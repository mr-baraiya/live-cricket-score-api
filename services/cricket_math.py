import math
from typing import Optional, Union


def overs_to_balls(overs: Optional[Union[float, int, str]]) -> Optional[int]:
    """
    Converts cricket overs representation (e.g. 17.4 or "17.4") into total legal balls (106).
    In cricket, 17.4 means 17 overs and 4 balls.
    """
    if overs is None:
        return None

    try:
        s_overs = str(overs).strip()
        if not s_overs:
            return None

        if "." in s_overs:
            parts = s_overs.split(".")
            completed_overs = int(parts[0])
            balls_in_over = int(parts[1]) if parts[1] else 0
            if balls_in_over > 5:
                # Fallback if illegal ball count given
                balls_in_over = 5
            return (completed_overs * 6) + balls_in_over
        else:
            completed_overs = int(s_overs)
            return completed_overs * 6
    except (ValueError, TypeError):
        return None


def balls_to_overs_display(total_balls: Optional[int]) -> Optional[float]:
    """
    Converts total legal balls (e.g. 106) into cricket overs display float (e.g. 17.4).
    """
    if total_balls is None or total_balls < 0:
        return None

    completed_overs = total_balls // 6
    remaining_balls = total_balls % 6
    if remaining_balls == 0:
        return float(completed_overs)
    return float(f"{completed_overs}.{remaining_balls}")


def calculate_run_rate(runs: Optional[int], overs: Optional[Union[float, int, str]]) -> Optional[float]:
    """
    Calculates cricket run-rate using ball-count mathematics.
    Formula: runs / (total_balls / 6.0)
    """
    if runs is None or runs < 0:
        return None

    total_balls = overs_to_balls(overs)
    if not total_balls or total_balls <= 0:
        return None

    overs_exact = total_balls / 6.0
    return round(runs / overs_exact, 2)


def validate_runs(runs: Optional[int]) -> Optional[int]:
    if runs is not None and isinstance(runs, int) and runs >= 0:
        return runs
    return None


def validate_wickets(wickets: Optional[int]) -> Optional[int]:
    if wickets is not None and isinstance(wickets, int) and 0 <= wickets <= 10:
        return wickets
    return None
