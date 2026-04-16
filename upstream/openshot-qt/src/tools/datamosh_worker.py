#!/usr/bin/env python3
"""Minimal subprocess worker for vendored Datamosher-Pro algorithms."""

import argparse
import os
import sys

AMOUNT_DEFAULT_KEY = "default"
AMOUNT_OPTIONS = {"light", AMOUNT_DEFAULT_KEY, "wild"}


def _bootstrap_vendor_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    upstream_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    vendor_root = os.path.join(upstream_root, "datamosher-pro", "Python Version")
    if vendor_root not in sys.path:
        sys.path.insert(0, vendor_root)


def _normalize_amount(amount_key):
    normalized = str(amount_key or AMOUNT_DEFAULT_KEY)
    if normalized not in AMOUNT_OPTIONS:
        return AMOUNT_DEFAULT_KEY
    return normalized


def run_worker(mode, input_path, output_path, amount_key=AMOUNT_DEFAULT_KEY):
    _bootstrap_vendor_path()
    from DatamoshLib.Original import classic, classic_new, repeat
    from DatamoshLib.Tomato import tomato

    amount_key = _normalize_amount(amount_key)

    if mode == "void_cut":
        kill_amount = {
            "light": 0.78,
            AMOUNT_DEFAULT_KEY: 0.6,
            "wild": 0.42,
        }[amount_key]
        tomato.mosh(input_path, output_path, m="void", c=1, n=1, a=0, f=1, k=kill_amount)
        return
    if mode == "jiggle_pulse":
        jiggle_amount = {
            "light": 2,
            AMOUNT_DEFAULT_KEY: 4,
            "wild": 7,
        }[amount_key]
        kill_amount = {
            "light": 0.75,
            AMOUNT_DEFAULT_KEY: 0.6,
            "wild": 0.45,
        }[amount_key]
        tomato.mosh(input_path, output_path, m="jiggle", c=1, n=jiggle_amount, a=0, f=1, k=kill_amount)
        return
    if mode == "classic_melt":
        repeat_frames = {
            "light": 1,
            AMOUNT_DEFAULT_KEY: 1,
            "wild": 2,
        }[amount_key]
        if repeat_frames <= 1:
            classic_new.Datamosh(input_path, output_path, s=1, e=-1, fps=30)
        else:
            classic.Datamosh(input_path, output_path, s=0, e=999, p=repeat_frames, fps=30)
        return
    if mode == "repeat_melt":
        repeat_amount = {
            "light": 3,
            AMOUNT_DEFAULT_KEY: 5,
            "wild": 8,
        }[amount_key]
        repeat.Datamosh(input_path, output_path, s=1, e=-1, p=repeat_amount, fps=30)
        return
    raise ValueError("Unsupported datamosh mode: {}".format(mode))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode")
    parser.add_argument("--amount", default=AMOUNT_DEFAULT_KEY)
    parser.add_argument("input_path")
    parser.add_argument("output_path")
    args = parser.parse_args()
    run_worker(args.mode, args.input_path, args.output_path, amount_key=args.amount)


if __name__ == "__main__":
    main()
