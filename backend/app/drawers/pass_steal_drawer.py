import cv2

class PassStealDrawer:
    def __init__(self):
        pass

    def get_stats(self, passes, steals):
        team1_passes = []
        team2_passes = []
        team1_steals = []
        team2_steals = []

        for frame_num in range(len(passes)):
            if passes[frame_num] == 1:
                team1_passes.append(frame_num)
            elif passes[frame_num] == 2:
                team2_passes.append(frame_num)
                
            if steals[frame_num] == 1:
                team1_steals.append(frame_num)
            elif steals[frame_num] == 2:
                team2_steals.append(frame_num)
                
        return len(team1_passes), len(team2_passes), len(team1_steals), len(team2_steals)


    def draw(self, video_frames, passes, steals):
        output_video_frames = []

        for frame_num, frame in enumerate(video_frames):

            frame_drawn = self.draw_frame(frame, frame_num, passes, steals)
            output_video_frames.append(frame_drawn)

        return output_video_frames
    
    def draw_frame(self, frame, frame_num, passes, steals):
        overlay = frame.copy()
        font_scale = 0.7
        font_thickness = 2

        # overlay position
        frame_height, frame_width = overlay.shape[:2]
        rect_x1 = int(frame_width * 0.16)
        rect_y1 = int(frame_height * 0.75)
        rect_x2 = int(frame_width * 0.55)
        rect_y2 = int(frame_height * 0.90)

        # text position
        text_x = int(frame_width * 0.19)
        text_y1 = int(frame_height * 0.80)
        text_y2 = int(frame_height * 0.88)

        cv2.rectangle(overlay, (rect_x1, rect_y1), (rect_x2, rect_y2), (255,255,255), -1)
        alpha = 0.8
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        passes_till_frame = passes[:frame_num + 1]
        steals_till_frame = steals[:frame_num + 1]

        team_1_passes, team_2_passes, team_1_steals, team_2_steals = self.get_stats(passes_till_frame, steals_till_frame)

        cv2.putText(
            frame, 
            f"Team 1 - Passes: {team_1_passes} Steals: {team_1_steals}",
            (text_x, text_y1), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            font_scale, 
            (0,0,0), 
            font_thickness
        )
        
        cv2.putText(
            frame, 
            f"Team 2 - Passes: {team_2_passes} Steals: {team_2_steals}",
            (text_x, text_y2), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            font_scale, 
            (0,0,0), 
            font_thickness
        )

        return frame
