"""``CycleDetector`` — iterative three-colour DFS cycle detector for knot subgraphs."""

from __future__ import annotations

from collections.abc import Iterator


class CycleDetector:
    """DFS-based cycle detector for knot subgraphs.

    Stateless utility wrapping the three-color DFS: 0=white, 1=grey,
    2=black.  Exposed as static methods so call sites do not need to
    instantiate the detector.

    The walk is **iterative**.  It used to recurse one Python frame per graph
    level, which capped usable graph depth at roughly 980 knots — the engine
    validates the graph on every run, so a deep chain died with a
    ``RecursionError`` before executing.  ``LoopSubTapestry`` chains iterations
    through parent edges, one level per iteration, so an open-ended
    conversational loop hit that ceiling in the ordinary course of doing its
    job.  Measured: DFS depth tracks iteration count 1:1.  See PIR-766/PIR-763.
    """

    @staticmethod
    def detect(knot_ids: list[str], children_by_parent: dict[str, list[str]]) -> bool:
        """Return True if the graph contains a cycle.

        Iterative three-colour DFS: 0=white (unvisited), 1=grey (on the current
        path), 2=black (fully explored).  An edge to a grey node closes a cycle.

        Args:
            knot_ids: The nodes to use as DFS roots.
            children_by_parent: Adjacency mapping.  Children absent from
                ``knot_ids`` are treated as white and explored, matching the
                previous recursive implementation.

        Returns:
            True if the graph contains a cycle reachable from any root.
        """
        color: dict[str, int] = {kid: 0 for kid in knot_ids}
        for root in list(color.keys()):
            if color[root] != 0:
                continue
            color[root] = 1
            # Each frame is the node plus its *partially consumed* child
            # iterator, which is what lets the walk resume where it left off
            # after descending — the explicit stand-in for a call stack.
            stack: list[tuple[str, Iterator[str]]] = [
                (root, iter(children_by_parent.get(root, [])))
            ]
            while stack:
                node, children = stack[-1]
                descended = False
                for child_id in children:
                    state = color.get(child_id, 0)
                    if state == 1:
                        return True
                    if state == 0:
                        color[child_id] = 1
                        stack.append((child_id, iter(children_by_parent.get(child_id, []))))
                        descended = True
                        break
                if not descended:
                    color[node] = 2
                    stack.pop()
        return False
