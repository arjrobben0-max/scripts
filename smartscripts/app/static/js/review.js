/**
 * Highlight low-confidence OCR text and keywords.
 * 
 * @param {string} text - The OCR text block
 * @param {number} confidence - Confidence score (0–1)
 * @returns {string} - HTML string with <mark> highlights
 */
function highlightLowConfidence(text, confidence = 1.0) {
    let highlighted = text;

    // Highlight keywords (case-insensitive)
    const keywords = ["Name", "ID"];
    keywords.forEach(keyword => {
        const regex = new RegExp(`(${keyword})`, "gi");
        highlighted = highlighted.replace(regex, `<mark class="keyword">$1</mark>`);
    });

    // If confidence is low, wrap entire text in warning style
    if (confidence < 0.6) {
        highlighted = `<span class="low-confidence">${highlighted}</span>`;
    }

    return highlighted;
}
