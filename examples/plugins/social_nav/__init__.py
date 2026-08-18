"""A local plugin that lives outside the registry (H6, proof 1).

Nothing in ``planbench_benchmark.registry`` mentions it, nothing in
``run_stack`` branches for it. The platform learns it exists by reading
its manifest and running it through the host.
"""

from social_nav.planner import SocialNavPlanner

__all__ = ["SocialNavPlanner"]
