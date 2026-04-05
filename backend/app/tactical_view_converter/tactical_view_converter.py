# from copy import deepcopy
# import numpy as np
# import cv2
# import sys
# from .homography import Homography
# sys.path.append("../")
# from utils import measure_distance, get_foot_position

# class TacticalViewConverter:
#     def __init__(self, court_image_path):
#         self.court_image_path=court_image_path
#         self.width=300
#         self.height=161
        
#         self.actual_width_in_meters=28
#         self.actual_height_in_meters=15

#         self.key_points = [
#             # left edge
#             (0,0),
#             (0,int((0.91/self.actual_height_in_meters)*self.height)),
#             (0,int((5.18/self.actual_height_in_meters)*self.height)),
#             (0,int((10/self.actual_height_in_meters)*self.height)),
#             (0,int((14.1/self.actual_height_in_meters)*self.height)),
#             (0,int(self.height)),

#             # Middle line
#             (int(self.width/2),self.height),
#             (int(self.width/2),0),
            
#             # Left Free throw line
#             (int((5.79/self.actual_width_in_meters)*self.width),int((5.18/self.actual_height_in_meters)*self.height)),
#             (int((5.79/self.actual_width_in_meters)*self.width),int((10/self.actual_height_in_meters)*self.height)),

#             # right edge
#             (self.width,int(self.height)),
#             (self.width,int((14.1/self.actual_height_in_meters)*self.height)),
#             (self.width,int((10/self.actual_height_in_meters)*self.height)),
#             (self.width,int((5.18/self.actual_height_in_meters)*self.height)),
#             (self.width,int((0.91/self.actual_height_in_meters)*self.height)),
#             (self.width,0),

#             # Right Free throw line
#             (int(((self.actual_width_in_meters-5.79)/self.actual_width_in_meters)*self.width),int((5.18/self.actual_height_in_meters)*self.height)),
#             (int(((self.actual_width_in_meters-5.79)/self.actual_width_in_meters)*self.width),int((10/self.actual_height_in_meters)*self.height)),
#         ]

#     def validate_keypoints(self, keypoints_list):
#         keypoints_list = deepcopy(keypoints_list)
        
#         for frame_idx, frame_keypoints in enumerate(keypoints_list):
#             if frame_keypoints is None or len(frame_keypoints.xy) == 0:
#                 continue

#             frame_keypoints = frame_keypoints.xy.tolist()[0]

#             detected_indices = [i for i, kp in enumerate(frame_keypoints) if kp[0] > 0 and kp[1] > 0]

#             if len(detected_indices) < 3:
#                 continue

#             invalid_keypoints = []

#             for i in detected_indices:
#                 # skip (0, 0) keypoints
#                 if frame_keypoints[i][0] == 0 and frame_keypoints[i][1] == 0:
#                     continue

#                 other_indices = [idx for idx in detected_indices if idx != i and idx not in invalid_keypoints]

#                 if len(other_indices) < 2:
#                     continue

#                 j, k = other_indices[0], other_indices[1]

#                 detected_ij = measure_distance(frame_keypoints[i], frame_keypoints[j])
#                 detected_ik = measure_distance(frame_keypoints[i], frame_keypoints[k])

#                 tactical_ij = measure_distance(self.key_points[i], self.key_points[j])
#                 tactical_ik = measure_distance(self.key_points[i], self.key_points[k])

#                 if tactical_ij > 0 and tactical_ik > 0:
#                     proportion_detected = detected_ij / detected_ik if detected_ik > 0 else float('inf')
#                     proportion_tactical = tactical_ij / tactical_ik if tactical_ik > 0 else float('inf')

#                     error = (proportion_detected - proportion_tactical) / proportion_tactical
#                     error = abs(error)

#                     if error > 0.65:
#                         keypoints_list[frame_idx].xy[0][i] *= 0
#                         keypoints_list[frame_idx].xyn[0][i] *= 0
#                         invalid_keypoints.append(i)

#         return keypoints_list


from copy import deepcopy
from itertools import combinations
import numpy as np
import math
import cv2
import sys
from .homography import Homography
sys.path.append("../")
from utils import measure_distance, get_foot_position


class TacticalViewConverter:
    def __init__(self, court_image_path):
        self.court_image_path = court_image_path
        self.width = 300
        self.height = 161

        self.actual_width_in_meters = 28
        self.actual_height_in_meters = 15

        self.key_points = [
            # left edge
            (0, 0),
            (0, int((0.91 / self.actual_height_in_meters) * self.height)),
            (0, int((5.18 / self.actual_height_in_meters) * self.height)),
            (0, int((10 / self.actual_height_in_meters) * self.height)),
            (0, int((14.1 / self.actual_height_in_meters) * self.height)),
            (0, int(self.height)),

            # middle line
            (int(self.width / 2), self.height),
            (int(self.width / 2), 0),

            # left free throw line
            (int((5.79 / self.actual_width_in_meters) * self.width),
             int((5.18 / self.actual_height_in_meters) * self.height)),
            (int((5.79 / self.actual_width_in_meters) * self.width),
             int((10 / self.actual_height_in_meters) * self.height)),

            # right edge
            (self.width, int(self.height)),
            (self.width, int((14.1 / self.actual_height_in_meters) * self.height)),
            (self.width, int((10 / self.actual_height_in_meters) * self.height)),
            (self.width, int((5.18 / self.actual_height_in_meters) * self.height)),
            (self.width, int((0.91 / self.actual_height_in_meters) * self.height)),
            (self.width, 0),

            # right free throw line
            (int(((self.actual_width_in_meters - 5.79) / self.actual_width_in_meters) * self.width),
             int((5.18 / self.actual_height_in_meters) * self.height)),
            (int(((self.actual_width_in_meters - 5.79) / self.actual_width_in_meters) * self.width),
             int((10 / self.actual_height_in_meters) * self.height)),
        ]

        self.left_edge_indices = [0, 1, 2, 3, 4, 5]
        self.center_indices = [6, 7]
        self.left_free_throw_indices = [8, 9]
        self.right_edge_indices = [10, 11, 12, 13, 14, 15]
        self.right_free_throw_indices = [16, 17]

    def _invalidate_keypoint(self, keypoints, keypoint_index):
        keypoints.xy[0][keypoint_index] *= 0
        keypoints.xyn[0][keypoint_index] *= 0
        if hasattr(keypoints, "conf") and keypoints.conf is not None:
            keypoints.conf[0][keypoint_index] *= 0

    def _is_visible(self, keypoints, index, conf_threshold=0.0):
        x, y = keypoints.xy.tolist()[0][index]
        if x <= 0 or y <= 0:
            return False

        if hasattr(keypoints, "conf") and keypoints.conf is not None:
            conf = keypoints.conf.tolist()[0][index]
            if conf < conf_threshold:
                return False

        return True

    def _get_visible_indices(self, keypoints, conf_threshold=0.0):
        return [
            i for i in range(len(keypoints.xy.tolist()[0]))
            if self._is_visible(keypoints, i, conf_threshold)
        ]

    def _remove_invalid_side_assignments(self, keypoints):
        normalized_keypoints = keypoints.xyn.tolist()[0]

        # Safe tightening:
        # left threshold 0.62 -> 0.58
        # right threshold 0.38 -> 0.42
        # center range 0.20-0.80 -> 0.25-0.75

        for index in self.left_edge_indices + self.left_free_throw_indices:
            if normalized_keypoints[index][0] > 0.58:
                self._invalidate_keypoint(keypoints, index)

        for index in self.right_edge_indices + self.right_free_throw_indices:
            if 0 < normalized_keypoints[index][0] < 0.42:
                self._invalidate_keypoint(keypoints, index)

        for index in self.center_indices:
            if normalized_keypoints[index][0] > 0 and not 0.25 <= normalized_keypoints[index][0] <= 0.75:
                self._invalidate_keypoint(keypoints, index)

    def _soft_order_score(self, keypoints):
        pts = keypoints.xyn.tolist()[0]
        penalties = {}

        groups = [
            self.left_edge_indices,
            list(reversed(self.right_edge_indices)),
        ]

        for group in groups:
            visible = [idx for idx in group if pts[idx][0] > 0 and pts[idx][1] > 0]
            for a, b in zip(visible, visible[1:]):
                if pts[b][1] < pts[a][1]:
                    penalties[a] = penalties.get(a, 0) + 1
                    penalties[b] = penalties.get(b, 0) + 1

        if self._is_visible(keypoints, 8) and self._is_visible(keypoints, 9):
            if pts[8][1] >= pts[9][1]:
                penalties[8] = penalties.get(8, 0) + 1
                penalties[9] = penalties.get(9, 0) + 1

        if self._is_visible(keypoints, 16) and self._is_visible(keypoints, 17):
            if pts[16][1] >= pts[17][1]:
                penalties[16] = penalties.get(16, 0) + 1
                penalties[17] = penalties.get(17, 0) + 1

        if self._is_visible(keypoints, 6) and self._is_visible(keypoints, 7):
            if pts[7][1] >= pts[6][1]:
                penalties[6] = penalties.get(6, 0) + 1
                penalties[7] = penalties.get(7, 0) + 1

        return penalties

    def _score_geometric_outliers(
        self,
        keypoints,
        conf_threshold=0.0,
        min_support_pairs=5,
        min_reference_distance=12.0
    ):
        frame_keypoints = keypoints.xy.tolist()[0]
        visible_indices = self._get_visible_indices(keypoints, conf_threshold)
        scores = {}

        if len(visible_indices) < 5:
            return scores

        for index in visible_indices:
            reference_indices = [j for j in visible_indices if j != index]
            errors = []

            for ref_a, ref_b in combinations(reference_indices, 2):
                detected_a = measure_distance(frame_keypoints[index], frame_keypoints[ref_a])
                detected_b = measure_distance(frame_keypoints[index], frame_keypoints[ref_b])

                tactical_a = measure_distance(self.key_points[index], self.key_points[ref_a])
                tactical_b = measure_distance(self.key_points[index], self.key_points[ref_b])

                if min(detected_a, detected_b, tactical_a, tactical_b) < min_reference_distance:
                    continue

                detected_ratio = detected_a / detected_b
                tactical_ratio = tactical_a / tactical_b

                if detected_ratio <= 0 or tactical_ratio <= 0:
                    continue

                errors.append(abs(math.log(detected_ratio / tactical_ratio)))

            if len(errors) >= min_support_pairs:
                errors.sort()
                median = errors[len(errors) // 2]

                low = int(len(errors) * 0.2)
                high = max(low + 1, int(len(errors) * 0.8))
                trimmed = errors[low:high]
                trimmed_mean = sum(trimmed) / len(trimmed)

                scores[index] = 0.5 * median + 0.5 * trimmed_mean

        return scores

    def _remove_only_worst_geometric_outlier(
        self,
        keypoints,
        error_threshold=0.50,
        conf_threshold=0.0,
        min_support_pairs=5
    ):
        scores = self._score_geometric_outliers(
            keypoints=keypoints,
            conf_threshold=conf_threshold,
            min_support_pairs=min_support_pairs,
        )

        if not scores:
            return

        worst_index = max(scores, key=scores.get)
        worst_score = scores[worst_index]

        second_worst_score = None
        if len(scores) > 1:
            sorted_scores = sorted(scores.values(), reverse=True)
            second_worst_score = sorted_scores[1]

        clearly_bad = (
            worst_score > error_threshold and
            (second_worst_score is None or worst_score - second_worst_score > 0.10)
        )

        if clearly_bad:
            self._invalidate_keypoint(keypoints, worst_index)

    def _remove_consensus_failures(self, keypoints, order_penalty_threshold=2, geom_threshold=0.65):
        order_penalties = self._soft_order_score(keypoints)
        geom_scores = self._score_geometric_outliers(keypoints)

        visible = self._get_visible_indices(keypoints)

        for idx in visible:
            order_bad = order_penalties.get(idx, 0) >= order_penalty_threshold
            geom_bad = geom_scores.get(idx, 0) > geom_threshold

            if order_bad and geom_bad:
                self._invalidate_keypoint(keypoints, idx)

    def _temporal_jump_filter(self, keypoints_list, jump_threshold=80):
        last_valid_positions = {}

        for keypoints in keypoints_list:
            if keypoints is None or len(keypoints.xy) == 0:
                continue

            pts = keypoints.xy.tolist()[0]

            for idx, (x, y) in enumerate(pts):
                if x <= 0 or y <= 0:
                    continue

                if idx in last_valid_positions:
                    prev_x, prev_y = last_valid_positions[idx]
                    jump = ((x - prev_x) ** 2 + (y - prev_y) ** 2) ** 0.5

                    if jump > jump_threshold:
                        continue

                last_valid_positions[idx] = (x, y)

    def validate_keypoints(self, keypoints_list):
        keypoints_list = deepcopy(keypoints_list)

        for frame_keypoints in keypoints_list:
            if frame_keypoints is None or len(frame_keypoints.xy) == 0:
                continue

            self._remove_invalid_side_assignments(frame_keypoints)
            self._remove_consensus_failures(frame_keypoints)
            self._remove_only_worst_geometric_outlier(frame_keypoints)

        self._temporal_jump_filter(keypoints_list)

        return keypoints_list



    def transform_players_to_tactical_view(self, keypoints_list, player_tracks):
        tactical_player_positions = []

        for frame_idx, (frame_keypoints, frame_tracks) in enumerate(zip(keypoints_list, player_tracks)):
            tactical_positions = {}

            if frame_keypoints is None or len(frame_keypoints.xy) == 0:
                continue

            frame_keypoints = frame_keypoints.xy.tolist()[0]

            if frame_keypoints is None or len(frame_keypoints) == 0:
                tactical_player_positions.append(tactical_positions)
                continue

            detected_keypoints = frame_keypoints

            valid_indices = [i for i, kp in enumerate(detected_keypoints) if kp[0] > 0 and kp[1] > 0]

            if len(valid_indices) < 4:
                tactical_player_positions.append(tactical_positions)
                continue

            source_points = np.array([detected_keypoints[i] for i in valid_indices], dtype=np.float32)
            target_points = np.array([self.key_points[i] for i in valid_indices], dtype=np.float32)

            try:
                homography = Homography(source_points, target_points)

                for player_id, player_data in frame_tracks.items():
                    bbox = player_data["bbox"]
                    player_position = np.array([get_foot_position(bbox)])

                    tactical_position = homography.transform_points(player_position)

                    tactical_positions[player_id] = tactical_position[0].tolist()


            except (ValueError, cv2.error) as e:
                pass
                
            tactical_player_positions.append(tactical_positions)

        return tactical_player_positions