#!/usr/bin/env python3

"""
find_astunpack.py

Convert MPC packed provisional designations to unpacked form.

The input may be either:

1. A file containing one packed provisional designation per line:

       K15BA9T
       _FB006U
       _FB006V

2. An MPC 80-column observation file, where the packed provisional
   designation occurs at the beginning of the line:

       K19V70E*4C2019 11 01.35808 02 22 48.55 -04 09 25.6 ...
       K19V70F*4C2019 11 02.27088 02 21 09.61 -04 53 35.2 ...

For MPC 80-column observation lines, everything except the packed
designation is ignored.

For extended packed provisional designations beginning with '_',
the original packed designation is appended after the unpacked form.

Example:

Input:
    K15BA9T
    _FB006U
    _FB006V

Output:
    2015 BT109
    2015 BC636 _FB006U
    2015 BD636 _FB006V

Usage:
    python find_astunpack.py input.txt output.txt

If output.txt is omitted, "_unpacked" is added to the input filename.
"""

import sys
from pathlib import Path


# Second provisional-designation letter.
# The letter I is omitted.
SECOND_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"

# Base-62 alphabet used by the extended packed format.
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# Extended format starts after 15,500 designations in a half-month.
EXTENDED_OFFSET = 15500


def base62_to_int(s):
    """Convert a base-62 string to an integer."""

    value = 0

    for char in s:
        if char not in BASE62:
            raise ValueError(
                f"Invalid base-62 character '{char}' in '{s}'"
            )

        value = value * 62 + BASE62.index(char)

    return value


def unpack_year_code(char):
    """
    Decode the year character of an extended packed designation.

    A = 2010
    B = 2011
    ...
    Z = 2035
    """

    if not ("A" <= char <= "Z"):
        raise ValueError(
            f"Invalid extended year code '{char}'"
        )

    return 2010 + ord(char) - ord("A")


def unpack_standard(packed):
    """
    Convert a standard 7-character packed provisional designation
    to its unpacked form.

    Example:
        K15BA9T -> 2015 BT109
    """

    if len(packed) != 7:
        raise ValueError(
            f"Packed designation must have 7 characters: '{packed}'"
        )

    year_code = packed[0]

    if year_code == "I":
        century = 1800
    elif year_code == "J":
        century = 1900
    elif year_code == "K":
        century = 2000
    else:
        raise ValueError(
            f"Unsupported packed year code '{year_code}' "
            f"in '{packed}'"
        )

    try:
        year = century + int(packed[1:3])
    except ValueError:
        raise ValueError(
            f"Invalid year in packed designation '{packed}'"
        )

    half_month = packed[3]

    if not ("A" <= half_month <= "Y"):
        raise ValueError(
            f"Invalid half-month letter '{half_month}' "
            f"in '{packed}'"
        )

    cycle_code = packed[4:6]
    second_letter = packed[6]

    if second_letter not in SECOND_LETTERS:
        raise ValueError(
            f"Invalid second designation letter "
            f"'{second_letter}' in '{packed}'"
        )

    # Decode the cycle number.
    #
    # 00 ... 99
    # A0 ... A9 = 100 ... 109
    # B0 ... B9 = 110 ... 119
    # ...
    if cycle_code.isdigit():

        cycle = int(cycle_code)

    else:

        first = cycle_code[0]

        if "A" <= first <= "Z":
            high = ord(first) - ord("A") + 10

        elif "a" <= first <= "z":
            high = ord(first) - ord("a") + 36

        else:
            raise ValueError(
                f"Invalid cycle code '{cycle_code}' "
                f"in '{packed}'"
            )

        if not cycle_code[1].isdigit():
            raise ValueError(
                f"Invalid cycle code '{cycle_code}' "
                f"in '{packed}'"
            )

        low = int(cycle_code[1])

        cycle = high * 10 + low

    if cycle == 0:
        cycle_string = ""
    else:
        cycle_string = str(cycle)

    return f"{year} {half_month}{second_letter}{cycle_string}"


def unpack_extended(packed):
    """
    Convert an extended packed provisional designation.

    Format:

        _YHBBBB

        _       extended-format marker
        Y       year code
        H       half-month
        BBBB    base-62 sequence

    Example:

        _FB006U -> 2015 BC636
        _FB006V -> 2015 BD636
    """

    if len(packed) != 7:
        raise ValueError(
            f"Extended designation must have 7 characters: "
            f"'{packed}'"
        )

    if not packed.startswith("_"):
        raise ValueError(
            f"Not an extended designation: '{packed}'"
        )

    year = unpack_year_code(packed[1])

    half_month = packed[2]

    if not ("A" <= half_month <= "Y"):
        raise ValueError(
            f"Invalid half-month letter '{half_month}' "
            f"in '{packed}'"
        )

    sequence = packed[3:7]

    sequence_number = base62_to_int(sequence)

    # The extended sequence starts after 15,500.
    order = EXTENDED_OFFSET + sequence_number

    # There are 25 possible second letters:
    # A B C D E F G H J K L M N O P Q R S T U V W X Y Z
    cycle, letter_index = divmod(order, 25)

    second_letter = SECOND_LETTERS[letter_index]

    if cycle == 0:
        cycle_string = ""
    else:
        cycle_string = str(cycle)

    return f"{year} {half_month}{second_letter}{cycle_string}"


def extract_packed_designation(line):
    """
    Extract a packed provisional designation from an input line.

    Leading whitespace is ignored.

    Accepted forms include:

        K15BA9T
        _FB006U

    and MPCOBS80-style lines such as:

        K19V70E*4C2019 11 01.35808 ...
        K19V70F*4C2019 11 02.27088 ...

    Only the first 7 characters of the non-whitespace part of the
    line are considered.

    Returns:
        packed designation, or None if the line does not contain one.
    """

    stripped = line.strip()

    if not stripped:
        return None

    # The packed designation is the first 7 characters.
    if len(stripped) < 7:
        return None

    candidate = stripped[:7]

    # Extended designation.
    if candidate[0] == "_":
        if len(candidate) == 7:
            return candidate
        return None

    # Standard packed designation:
    # first character is I/J/K,
    # followed by two digits,
    # then two letters,
    # then two packed cycle characters.
    if candidate[0] not in "IJK":
        return None

    if not candidate[1:3].isdigit():
        return None

    # The fourth character is the half-month letter.
    if not ("A" <= candidate[3] <= "Y"):
        return None

    # The final character must be one of the valid second letters.
    if candidate[6] not in SECOND_LETTERS:
        return None

    return candidate


def unpack_designation(packed):
    """Convert one packed designation to its unpacked form."""

    if packed.startswith("_"):
        return unpack_extended(packed)

    return unpack_standard(packed)


def process_file(input_file, output_file):
    """
    Process the input file.

    For normal packed designations:
        packed -> unpacked

    For extended designations:
        packed -> unpacked packed

    For MPCOBS80 lines:
        only the designation is output.
    """

    converted = 0
    skipped = 0

    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:

        for line_number, line in enumerate(fin, start=1):

            packed = extract_packed_designation(line)

            # Ignore blank or unrecognized lines.
            if packed is None:
                skipped += 1
                continue

            try:
                unpacked = unpack_designation(packed)

                if packed.startswith("_"):
                    # Extended designation:
                    # retain the original packed designation.
                    fout.write(
                        f"{unpacked} {packed}\n"
                    )
                else:
                    fout.write(
                        f"{unpacked}\n"
                    )

                converted += 1

            except ValueError as e:

                print(
                    f"Warning: line {line_number}: {e}",
                    file=sys.stderr
                )

                skipped += 1

    print(f"Converted: {converted}")

    if skipped:
        print(f"Ignored: {skipped}")

    print(f"Output: {output_file}")


def main():

    if len(sys.argv) not in (2, 3):

        print(
            "Usage: python find_astunpack.py "
            "input.txt [output.txt]"
        )

        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():

        print(
            f"Error: input file not found: {input_file}",
            file=sys.stderr
        )

        sys.exit(1)

    if len(sys.argv) == 3:

        output_file = Path(sys.argv[2])

    else:

        output_file = (
            input_file.parent
            / f"{input_file.stem}_unpacked{input_file.suffix}"
        )

    process_file(input_file, output_file)


if __name__ == "__main__":
    main()