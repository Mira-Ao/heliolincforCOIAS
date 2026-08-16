#!/usr/bin/env python3

import sys


# MPCORB fixed-width format
#
# Columns (1-based):
#   1-7     Number or provisional designation (packed)
#   93-103  Semimajor axis (AU)
#   118-122 Number of observations
#   124-126 Number of oppositions
#   167-194 Readable designation
#
# Python slices are 0-based and end-exclusive.


def parse_mpcorb_line(line):
    """
    Parse one MPCORB record.

    Returns:
        (packed_designation, readable_designation, semimajor_axis,
         number_of_observations, number_of_oppositions)

    Returns None for lines that cannot be parsed.
    """

    # Remove only the newline.
    line = line.rstrip("\r\n")

    # MPCORB records should be at least 126 columns for the fields
    # needed here.
    if len(line) < 126:
        return None

    # Skip blank lines.
    if not line.strip():
        return None

    try:
        packed_designation = line[0:7].strip()

        if not packed_designation:
            return None

        # Semimajor axis: columns 93-103
        semimajor_axis = float(line[92:103].strip())

        # Number of observations: columns 118-122
        nobs = int(line[117:122].strip())

        # Number of oppositions: columns 124-126
        nopp = int(line[123:126].strip())

        # Readable designation: columns 167-194
        if len(line) >= 194:
            readable_designation = line[166:194].strip()
        else:
            readable_designation = ""

        # If readable designation is unavailable, use packed designation.
        if not readable_designation:
            readable_designation = packed_designation

        return (
            packed_designation,
            readable_designation,
            semimajor_axis,
            nobs,
            nopp,
        )

    except (ValueError, IndexError):
        return None


def read_mpcorb(filename):
    """
    Read an MPCORB file and return a dictionary keyed by packed
    Number/provisional designation.
    """

    objects = {}
    skipped = 0
    duplicates = 0

    with open(filename, "r", encoding="ascii", errors="replace") as f:
        for line_number, line in enumerate(f, 1):

            # MPCORB files can contain header/comment lines.
            # Actual records begin with a non-blank designation in columns 1-7.
            record = parse_mpcorb_line(line)

            if record is None:
                skipped += 1
                continue

            (
                packed_designation,
                readable_designation,
                semimajor_axis,
                nobs,
                nopp,
            ) = record

            if packed_designation in objects:
                duplicates += 1

            objects[packed_designation] = {
                "packed": packed_designation,
                "name": readable_designation,
                "a": semimajor_axis,
                "nobs": nobs,
                "nopp": nopp,
            }

    if skipped > 0:
        print(
            f"Warning: {filename}: skipped {skipped} non-MPCORB/unreadable lines.",
            file=sys.stderr,
        )

    if duplicates > 0:
        print(
            f"Warning: {filename}: {duplicates} duplicate designation(s) found.",
            file=sys.stderr,
        )

    return objects


def main():

    if len(sys.argv) != 3:
        print(
            "Usage: python MPCORBdiff.py OLD_MPCORB NEW_MPCORB"
        )
        print()
        print("Example:")
        print(
            "  python MPCORBdiff.py MPCORB_old.dat MPCORB_new.dat"
        )
        sys.exit(1)

    old_file = sys.argv[1]
    new_file = sys.argv[2]

    print(f"Reading old MPCORB: {old_file}")
    old_data = read_mpcorb(old_file)

    print(f"Reading new MPCORB: {new_file}")
    new_data = read_mpcorb(new_file)

    print()
    print(f"Old file: {len(old_data):,} objects")
    print(f"New file: {len(new_data):,} objects")
    print()

    # ------------------------------------------------------------------
    # ① Objects whose number of oppositions changed from exactly 1
    #    in the old file to >= 2 in the new file.
    #
    #    IMPORTANT:
    #    Objects that were already >= 2 in the old file are NOT included,
    #    even if their number of oppositions increased.
    # ------------------------------------------------------------------

    newly_multi_opposition = []

    for designation, new_obj in new_data.items():

        if designation not in old_data:
            continue

        old_obj = old_data[designation]

        if old_obj["nopp"] == 1 and new_obj["nopp"] >= 2:
            newly_multi_opposition.append(
                (
                    new_obj["name"],
                    old_obj["nopp"],
                    new_obj["nopp"],
                )
            )

    newly_multi_opposition.sort(key=lambda x: x[0])

    print("=" * 72)
    print("① Objects changing from 1 opposition to 2 or more oppositions")
    print("=" * 72)

    if newly_multi_opposition:
        for name, old_nopp, new_nopp in newly_multi_opposition:
            print(f"{name}    {old_nopp} -> {new_nopp}")
    else:
        print("None")

    print()
    print(f"Number of objects: {len(newly_multi_opposition):,}")
    print()

    # ------------------------------------------------------------------
    # ② Objects with semimajor axis > 10 AU in the NEW MPCORB file
    #    whose number of oppositions increased.
    #
    #    This includes:
    #       old nopp = 1, new nopp = 2
    #       old nopp = 2, new nopp = 3
    #       old nopp = 3, new nopp = 5
    #       etc.
    #
    #    The semimajor axis criterion is applied to the NEW MPCORB.
    # ------------------------------------------------------------------

    large_a_opposition_increase = []

    for designation, new_obj in new_data.items():

        if designation not in old_data:
            continue

        old_obj = old_data[designation]

        if (
            new_obj["a"] > 10.0
            and new_obj["nopp"] > old_obj["nopp"]
        ):
            large_a_opposition_increase.append(
                (
                    new_obj["name"],
                    old_obj["nopp"],
                    new_obj["nopp"],
                    new_obj["a"],
                )
            )

    large_a_opposition_increase.sort(key=lambda x: x[3])

    print("=" * 72)
    print("② Objects with a > 10 AU and increased number of oppositions")
    print("=" * 72)

    if large_a_opposition_increase:
        for name, old_nopp, new_nopp, a in large_a_opposition_increase:
            print(
                f"{name}    "
                f"a={a:.7f} AU    "
                f"{old_nopp} -> {new_nopp}"
            )
    else:
        print("None")

    print()
    print(f"Number of objects: {len(large_a_opposition_increase):,}")
    print()

    # ------------------------------------------------------------------
    # Summary of objects that disappeared / appeared
    # ------------------------------------------------------------------

    old_keys = set(old_data.keys())
    new_keys = set(new_data.keys())

    only_old = old_keys - new_keys
    only_new = new_keys - old_keys

    print("=" * 72)
    print("Comparison summary")
    print("=" * 72)
    print(f"Objects in old file only: {len(only_old):,}")
    print(f"Objects in new file only: {len(only_new):,}")
    print(f"Objects common to both files: {len(old_keys & new_keys):,}")
    print()


if __name__ == "__main__":
    main()