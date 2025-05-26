

def convert_amount_to_words(amount):
    """Converts a numerical amount to words (Indian numbering system)."""
    if amount == 0:
        return "Zero"

    def twodigits(num):
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]

        if num < 10:
            return ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"][num]
        elif num < 20:
            return teens[num - 10]
        else:
            return tens[num // 10] + (" " + ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"][num % 10])

    def process(num):
        parts = []
        crores = num // 10000000
        num %= 10000000
        lakhs = num // 100000
        num %= 100000
        thousands = num // 1000
        num %= 1000
        hundreds = num // 100
        num %= 100
        tens = num

        if crores:
            parts.append(twodigits(crores) + " Crore")
        if lakhs:
            parts.append(twodigits(lakhs) + " Lakh")
        if thousands:
            parts.append(twodigits(thousands) + " Thousand")
        if hundreds:
            parts.append(twodigits(hundreds) + " Hundred")
        if tens:
            if parts:
                parts.append("and")
            parts.append(twodigits(tens))
        return " ".join(parts).strip()

    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)

    words = process(integer_part)

    if decimal_part > 0:
        words += f" and {twodigits(decimal_part)} Paise"

    return words
