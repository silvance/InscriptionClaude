"""Step generation: raw events -> draft procedural steps.

The generator is deterministic given the same inputs so regenerating steps
after capture is safe. It does four things:

1. Group raw events into "actions" (click + optional milestone key).
2. Suppress noise (double-clicks collapsed into one row, redundant window
   focus events dropped).
3. Produce human-readable draft text per action, pulling from the best
   available resolution signal (UIA control name > window title > generic).
4. Associate the most relevant screenshot with the step.
"""

from inscription.steps.generator import (
    StepGenerator,
    generate_steps,
    render_step_action,
)

__all__ = ["StepGenerator", "generate_steps", "render_step_action"]
