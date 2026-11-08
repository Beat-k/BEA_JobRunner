# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""BEA_JobRunner - lets an AI assistant run approved scripts on your own Linux machine and read the results back, with you in control."""
__version__ = "1.0.0"
from .config import DEFAULTS, load_config  # noqa: F401
from .policy import JobError, Plan, validate  # noqa: F401
from .trust import TrustStore  # noqa: F401
from .audit import AuditLog  # noqa: F401
from .runner import JobRunner, run_plan  # noqa: F401
