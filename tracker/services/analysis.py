import math


VISIBILITY_THRESHOLD = 0.45
KNEE_VALGUS_OFFSET = 0.03
SHALLOW_DEPTH_OFFSET = 0.02
FORWARD_LEAN_HIP_ANGLE = 60


def create_analysis_state():
    return {
        "total_frames": 0,
        "flagged_frames": 0,
        "rule_counts": {
            "knee_valgus": 0,
            "shallow_depth": 0,
            "forward_lean": 0,
        },
        "angle_sums": {
            "knee": 0.0,
            "hip": 0.0,
        },
        "angle_counts": {
            "knee": 0,
            "hip": 0,
        },
    }


def angle(a, b, c):
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.hypot(ba[0], ba[1])
    mag_bc = math.hypot(bc[0], bc[1])
    if mag_ba == 0 or mag_bc == 0:
        return None
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def build_summary(state):
    angle_sums = state["angle_sums"]
    angle_counts = state["angle_counts"]
    return {
        "rules": state["rule_counts"],
        "angles": {
            "knee_avg": round(angle_sums["knee"] / angle_counts["knee"], 1) if angle_counts["knee"] else None,
            "hip_avg": round(angle_sums["hip"] / angle_counts["hip"], 1) if angle_counts["hip"] else None,
        },
        "total_frames": state["total_frames"],
        "flagged_frames": state["flagged_frames"],
    }


def _point(landmark):
    return (landmark.x, landmark.y, landmark.visibility)


def extract_squat_points(landmarks, pose_landmark, visibility_threshold=VISIBILITY_THRESHOLD):
    points = {
        "left_hip": _point(landmarks[pose_landmark.LEFT_HIP]),
        "left_knee": _point(landmarks[pose_landmark.LEFT_KNEE]),
        "left_ankle": _point(landmarks[pose_landmark.LEFT_ANKLE]),
        "left_shoulder": _point(landmarks[pose_landmark.LEFT_SHOULDER]),
        "right_hip": _point(landmarks[pose_landmark.RIGHT_HIP]),
        "right_knee": _point(landmarks[pose_landmark.RIGHT_KNEE]),
        "right_ankle": _point(landmarks[pose_landmark.RIGHT_ANKLE]),
        "right_shoulder": _point(landmarks[pose_landmark.RIGHT_SHOULDER]),
    }

    if not all(point[2] > visibility_threshold for point in points.values()):
        return None

    return {
        name: (point[0], point[1])
        for name, point in points.items()
    }


def update_squat_analysis_state(state, points):
    knee_angle_left = angle(points["left_hip"], points["left_knee"], points["left_ankle"])
    knee_angle_right = angle(points["right_hip"], points["right_knee"], points["right_ankle"])
    hip_angle_left = angle(points["left_shoulder"], points["left_hip"], points["left_knee"])
    hip_angle_right = angle(points["right_shoulder"], points["right_hip"], points["right_knee"])

    knee_valgus = (
        points["left_knee"][0] > points["left_ankle"][0] + KNEE_VALGUS_OFFSET
        or points["right_knee"][0] < points["right_ankle"][0] - KNEE_VALGUS_OFFSET
    )
    shallow_depth = (
        points["left_hip"][1] <= points["left_knee"][1] - SHALLOW_DEPTH_OFFSET
        or points["right_hip"][1] <= points["right_knee"][1] - SHALLOW_DEPTH_OFFSET
    )
    forward_lean = (
        hip_angle_left is not None and hip_angle_left < FORWARD_LEAN_HIP_ANGLE
        or hip_angle_right is not None and hip_angle_right < FORWARD_LEAN_HIP_ANGLE
    )

    breached = False
    if knee_valgus:
        state["rule_counts"]["knee_valgus"] += 1
        breached = True
    if shallow_depth:
        state["rule_counts"]["shallow_depth"] += 1
        breached = True
    if forward_lean:
        state["rule_counts"]["forward_lean"] += 1
        breached = True
    if breached:
        state["flagged_frames"] += 1

    knee_angles = [value for value in [knee_angle_left, knee_angle_right] if value is not None]
    if knee_angles:
        state["angle_sums"]["knee"] += sum(knee_angles) / len(knee_angles)
        state["angle_counts"]["knee"] += 1

    hip_angles = [value for value in [hip_angle_left, hip_angle_right] if value is not None]
    if hip_angles:
        state["angle_sums"]["hip"] += sum(hip_angles) / len(hip_angles)
        state["angle_counts"]["hip"] += 1
