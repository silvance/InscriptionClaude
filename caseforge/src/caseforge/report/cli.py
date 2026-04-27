"""CLI for the report renderer.

Installed as ``caseforge-report`` so it's runnable independently of
the GUI — useful for batch generation, CI report builds, or pipelining
exports from a script.

Example::

    caseforge-report --template ./templates/forensic-summary.docx \\
                     --case ./cases/2026-CSAM-001 \\
                     --output ./reports/2026-CSAM-001.docx
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from caseforge import __version__
from caseforge.logging_setup import configure_logging
from caseforge.report.context import build_context
from caseforge.report.render import RenderError, render_report
from caseforge.storage import StorageError

logger = logging.getLogger("caseforge.report")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="caseforge-report",
        description="Render a DOCX template against a case directory.",
    )
    parser.add_argument(
        "--template",
        required=True,
        type=Path,
        help="Path to the .docx template (uses Jinja2 / docxtpl syntax).",
    )
    parser.add_argument(
        "--case",
        required=True,
        type=Path,
        help="Path to the case directory containing case.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the rendered .docx.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log at DEBUG instead of INFO.",
    )
    parser.add_argument(
        "--version", action="version", version=f"caseforge-report {__version__}"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    configure_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        context = build_context(args.case)
    except StorageError as exc:
        logger.error("Could not read case: %s", exc)
        return 2
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2

    try:
        render_report(
            template_path=args.template,
            context=context,
            output_path=args.output,
        )
    except RenderError as exc:
        logger.error("Render failed: %s", exc)
        return 3

    logger.info("Wrote %s", args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
