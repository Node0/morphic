"""
Dehyphenation processor for hOCR files.

This is a UNIQUE Morphic feature not found in OCRmyPDF or other OCR tools.

Problem: When books are typeset, long words at line endings are hyphenated:
    "The patient had difficulty retriev-
     ing memories from the experience."

OCR captures this as two separate words: "retriev-" and "ing"

For RAG systems, this is problematic because:
1. Search for "retrieving" won't find "retriev-" + "ing"
2. Embedding models see two fragments instead of one word
3. Text extraction produces broken words

Solution: Merge hyphenated word pairs using dictionary validation:
1. Find words ending with "-" at line endings
2. Find the first word of the next line
3. If combined word is in dictionary: merge them
4. Update hOCR bounding boxes to span merged text

This dramatically improves RAG retrieval quality for academic documents.
"""

from lxml import etree
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass
import copy

# Import utilities for logging
import sys
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
from utilities import Print

# Try to import enchant for dictionary validation
try:
    import enchant
    ENCHANT_AVAILABLE = True
except ImportError:
    ENCHANT_AVAILABLE = False
    Print("WARNING", "pyenchant not installed - dehyphenation will use heuristics only")


@dataclass
class BoundingBox:
    """Represents a bounding box from hOCR."""
    x1: int
    y1: int
    x2: int
    y2: int

    def merge_with(self, other: "BoundingBox") -> "BoundingBox":
        """Merge two bounding boxes into one encompassing box."""
        return BoundingBox(
            x1=min(self.x1, other.x1),
            y1=min(self.y1, other.y1),
            x2=max(self.x2, other.x2),
            y2=max(self.y2, other.y2)
        )

    def to_title_string(self) -> str:
        """Convert to hOCR title format."""
        return f"bbox {self.x1} {self.y1} {self.x2} {self.y2}"


@dataclass
class MergeCandidate:
    """Represents a potential hyphenation merge."""
    first_word_element: etree._Element
    second_word_element: etree._Element
    first_text: str  # e.g., "retriev-"
    second_text: str  # e.g., "ing"
    merged_text: str  # e.g., "retrieving"
    first_bbox: BoundingBox
    second_bbox: BoundingBox
    confidence: float  # 0.0 to 1.0


class Dehyphenator:
    """
    Process hOCR files to merge hyphenated words split across lines.

    This processor identifies words ending with hyphens at line breaks
    and merges them with the first word of the next line when the
    combined word is valid according to the dictionary.

    Attributes:
        enabled: Whether dehyphenation is active
        dictionary: Enchant dictionary for word validation
        min_word_length: Minimum length for merged words
        merge_strategy: How to handle the merged word in hOCR
    """

    def __init__(self, config: dict):
        """
        Initialize dehyphenator with configuration.

        Args:
            config: Configuration dictionary with optional keys:
                - enabled: bool - Enable/disable processing (default: True)
                - dictionary: str - Dictionary locale (default: 'en_US')
                - min_word_length: int - Minimum merged word length (default: 4)
        """
        self.enabled = config.get('enabled', True)
        self.min_word_length = config.get('min_word_length', 4)

        # Initialize dictionary if available
        dict_locale = config.get('dictionary', 'en_US')
        if ENCHANT_AVAILABLE:
            try:
                self.dictionary = enchant.Dict(dict_locale)
                Print("DEBUG", f"Dehyphenator initialized with {dict_locale} dictionary")
            except enchant.errors.DictNotFoundError:
                Print("WARNING", f"Dictionary '{dict_locale}' not found, trying 'en'")
                try:
                    self.dictionary = enchant.Dict('en')
                except:
                    self.dictionary = None
                    Print("WARNING", "No dictionary available - using heuristics only")
        else:
            self.dictionary = None

    def process_file(self, hocr_path: Path, output_path: Optional[Path] = None) -> int:
        """
        Process hOCR file to merge hyphenated words.

        Args:
            hocr_path: Path to input hOCR file
            output_path: Path for output (default: modify in place)

        Returns:
            Number of words merged
        """
        if not self.enabled:
            Print("DEBUG", "Dehyphenation disabled, skipping")
            return 0

        if output_path is None:
            output_path = hocr_path

        Print("DEBUG", f"Processing {hocr_path.name} for dehyphenation")

        # Parse hOCR
        tree = self._parse_hocr(hocr_path)
        if tree is None:
            return 0

        # Find merge candidates
        candidates = self._find_merge_candidates(tree)

        if not candidates:
            Print("DEBUG", "No hyphenated words found")
            return 0

        Print("DEBUG", f"Found {len(candidates)} potential merges")

        # Apply merges
        merged_count = self._apply_merges(tree, candidates)

        # Write output
        if merged_count > 0:
            self._write_hocr(tree, output_path)
            Print("INFO", f"Merged {merged_count} hyphenated words in {hocr_path.name}")

        return merged_count

    def _parse_hocr(self, hocr_path: Path) -> Optional[etree._ElementTree]:
        """Parse hOCR file into lxml tree."""
        try:
            # Try XML parser first (preserves namespaces)
            try:
                return etree.parse(str(hocr_path))
            except etree.XMLSyntaxError:
                # Fall back to HTML parser
                parser = etree.HTMLParser(recover=True)
                return etree.parse(str(hocr_path), parser)
        except Exception as e:
            Print("FAILURE", f"Failed to parse hOCR: {e}")
            return None

    def _find_merge_candidates(self, tree: etree._ElementTree) -> List[MergeCandidate]:
        """
        Find all potential hyphenated word pairs for merging.

        Scans through lines looking for:
        1. Last word of line ending with "-"
        2. First word of next line

        Then validates that the merged word is legitimate.
        """
        candidates = []

        # Namespace handling for XHTML hOCR
        ns = {'x': 'http://www.w3.org/1999/xhtml'}

        # Get all lines
        lines = tree.xpath('//x:span[@class="ocr_line"]', namespaces=ns)
        if not lines:
            lines = tree.xpath('//*[@class="ocr_line"]')

        if not lines:
            Print("DEBUG", "No lines found in hOCR")
            return candidates

        # Process consecutive line pairs
        for i in range(len(lines) - 1):
            current_line = lines[i]
            next_line = lines[i + 1]

            # Get words in each line
            current_words = current_line.xpath('.//x:span[@class="ocrx_word"]', namespaces=ns)
            if not current_words:
                current_words = current_line.xpath('.//*[@class="ocrx_word"]')

            next_words = next_line.xpath('.//x:span[@class="ocrx_word"]', namespaces=ns)
            if not next_words:
                next_words = next_line.xpath('.//*[@class="ocrx_word"]')

            if not current_words or not next_words:
                continue

            # Get last word of current line and first word of next line
            last_word = current_words[-1]
            first_word = next_words[0]

            last_text = self._get_word_text(last_word)
            first_text = self._get_word_text(first_word)

            if not last_text or not first_text:
                continue

            # Check if last word ends with hyphen
            if not last_text.endswith('-'):
                continue

            # Create candidate
            candidate = self._evaluate_merge_candidate(
                last_word, first_word, last_text, first_text
            )

            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _evaluate_merge_candidate(
        self,
        first_elem: etree._Element,
        second_elem: etree._Element,
        first_text: str,
        second_text: str
    ) -> Optional[MergeCandidate]:
        """
        Evaluate if a word pair should be merged.

        Returns MergeCandidate if valid, None otherwise.
        """
        # Remove hyphen and merge
        base_text = first_text.rstrip('-')
        merged_text = base_text + second_text

        # Basic length check
        if len(merged_text) < self.min_word_length:
            return None

        # Validate with dictionary if available
        confidence = 0.5  # Default confidence without dictionary

        if self.dictionary:
            if self.dictionary.check(merged_text):
                confidence = 0.95
            elif self.dictionary.check(merged_text.lower()):
                confidence = 0.90
            else:
                # Check if it could be a valid word with suggestions
                suggestions = self.dictionary.suggest(merged_text)
                if merged_text.lower() in [s.lower() for s in suggestions[:5]]:
                    confidence = 0.7
                else:
                    # Not in dictionary - likely not a valid merge
                    Print("DEBUG", f"Rejected merge: '{first_text}' + '{second_text}' = '{merged_text}' (not in dictionary)")
                    return None
        else:
            # Heuristic validation without dictionary
            # Accept if it looks like a reasonable word
            if not merged_text.isalpha() and not merged_text.replace("'", "").isalpha():
                return None
            confidence = 0.6

        # Parse bounding boxes
        first_bbox = self._parse_bbox(first_elem.get('title', ''))
        second_bbox = self._parse_bbox(second_elem.get('title', ''))

        Print("DEBUG", f"Candidate merge: '{first_text}' + '{second_text}' = '{merged_text}' (confidence: {confidence:.2f})")

        return MergeCandidate(
            first_word_element=first_elem,
            second_word_element=second_elem,
            first_text=first_text,
            second_text=second_text,
            merged_text=merged_text,
            first_bbox=first_bbox,
            second_bbox=second_bbox,
            confidence=confidence
        )

    def _apply_merges(self, tree: etree._ElementTree, candidates: List[MergeCandidate]) -> int:
        """
        Apply all valid merges to the hOCR tree.

        Strategy: Update first word with merged text, remove second word.
        This preserves the first word's position in document flow.
        """
        merged_count = 0

        for candidate in candidates:
            if candidate.confidence < 0.5:
                continue

            try:
                # Update first word element
                first_elem = candidate.first_word_element
                second_elem = candidate.second_word_element

                # Set merged text on first word
                # Clear existing text and set new text
                first_elem.text = candidate.merged_text
                # Remove any child elements' text
                for child in first_elem:
                    child.text = None
                    child.tail = None

                # Update bounding box - merge the two boxes
                merged_bbox = candidate.first_bbox.merge_with(candidate.second_bbox)

                # Preserve other title attributes (like x_wconf)
                old_title = first_elem.get('title', '')
                new_title = self._update_bbox_in_title(old_title, merged_bbox)
                first_elem.set('title', new_title)

                # Remove second word element
                parent = second_elem.getparent()
                if parent is not None:
                    parent.remove(second_elem)

                Print("DEBUG", f"Merged: '{candidate.first_text}' + '{candidate.second_text}' -> '{candidate.merged_text}'")
                merged_count += 1

            except Exception as e:
                Print("WARNING", f"Failed to merge '{candidate.first_text}' + '{candidate.second_text}': {e}")

        return merged_count

    def _get_word_text(self, element: etree._Element) -> str:
        """Extract text content from a word element."""
        # Get all text including from child elements
        text_parts = []
        if element.text:
            text_parts.append(element.text)
        for child in element:
            if child.text:
                text_parts.append(child.text)
            if child.tail:
                text_parts.append(child.tail)
        return ''.join(text_parts).strip()

    def _parse_bbox(self, title: str) -> BoundingBox:
        """Parse bounding box from hOCR title attribute."""
        if not title:
            return BoundingBox(0, 0, 0, 0)

        try:
            # Extract bbox part (before semicolon)
            bbox_part = title.split(';')[0].strip()
            parts = bbox_part.split()

            if len(parts) >= 5 and parts[0] == 'bbox':
                return BoundingBox(
                    x1=int(parts[1]),
                    y1=int(parts[2]),
                    x2=int(parts[3]),
                    y2=int(parts[4])
                )
        except (ValueError, IndexError):
            pass

        return BoundingBox(0, 0, 0, 0)

    def _update_bbox_in_title(self, title: str, bbox: BoundingBox) -> str:
        """Update the bbox in a title string while preserving other attributes."""
        if not title:
            return bbox.to_title_string()

        # Split on semicolons to get individual attributes
        parts = title.split(';')

        # Replace or add bbox
        new_parts = []
        bbox_found = False

        for part in parts:
            part = part.strip()
            if part.startswith('bbox'):
                new_parts.append(bbox.to_title_string())
                bbox_found = True
            elif part:
                new_parts.append(part)

        if not bbox_found:
            new_parts.insert(0, bbox.to_title_string())

        return '; '.join(new_parts)

    def _write_hocr(self, tree: etree._ElementTree, output_path: Path) -> None:
        """Write modified hOCR tree to file."""
        try:
            tree.write(
                str(output_path),
                encoding='utf-8',
                xml_declaration=True,
                pretty_print=True
            )
        except Exception as e:
            Print("FAILURE", f"Failed to write hOCR: {e}")
            raise

    @property
    def name(self) -> str:
        """Processor identifier."""
        return "dehyphenator"
