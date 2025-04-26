bl_info = {
    "name": "VSE Extend Strips to Next",
    "author": "tintwotin", # Update author
    "version": (1, 6), # Increment version number
    "blender": (4, 0, 0), # Specify minimum Blender version
    "location": "Sequencer > Strip > Transform",
    "description": "Extends selected strip ends to the frame before the next strip in the same channel (within 1000 frames), processing by channel then time.",
    "category": "Sequencer",
}

import bpy

class SEQUENCER_OT_extend_to_next_strip(bpy.types.Operator):
    """Extend selected strip end to the frame before the next strip in the same channel (within 1000 frames)"""
    bl_idname = "sequencer.extend_to_next_strip"
    bl_label = "Extend to Next Strip in Channel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Operator is available if a sequence editor exists in the current scene.
        return context.scene and context.scene.sequence_editor is not None

    def execute(self, context):
        scene = context.scene

        # Use context.sequences and context.selected_sequences for meta stack compatibility.
        # These properties automatically refer to the strips at the currently active
        # meta stack level or the main timeline.
        strips_at_level = context.sequences
        selected_strips = context.selected_sequences

        if not selected_strips:
            self.report({'INFO'}, "No strips selected.")
            return {'CANCELLED'}

        # --- Core Change: Sort the selected strips by channel, then by start frame ---
        # This ensures we process strips from lowest channel up, and from left to right within each channel.
        # Use sorted() to create a new list, avoiding modification of context.selected_sequences in-place.
        sorted_selected_strips = sorted(selected_strips, key=lambda s: (s.channel, s.frame_start))
        # --- End of Core Change ---


        # Get all strips at the current meta stack level and sort them by start frame.
        # This list is used *inside* the loop to efficiently find the *true* next strip
        # in the same channel for the *current* strip being processed from the sorted_selected_strips list.
        all_strips_sorted_by_time = list(strips_at_level)
        all_strips_sorted_by_time.sort(key=lambda s: s.frame_start)

        print(f"Processing {len(sorted_selected_strips)} selected strips, sorted by Channel then Start Frame...")

        processed_count = 0

        # Iterate over the newly sorted list of selected strips.
        for current_strip in sorted_selected_strips:

            # Find the current strip's position in the globally time-sorted list.
            # This is needed to efficiently search for the *next* strip after it.
            try:
                current_index_in_all = all_strips_sorted_by_time.index(current_strip)
            except ValueError:
                 # This can happen if a selected strip was somehow removed or isn't in the active context.sequences list.
                 print(f"Warning: Selected strip '{current_strip.name}' not found in the active sequence editor sequences list. Skipping.")
                 continue


            print(f"\nChecking strip: {current_strip.name} (Start: {current_strip.frame_start}, End: {current_strip.frame_final_end}, Channel: {current_strip.channel})")

            # Find the first strip in the same channel that starts *after* the current strip's *current* end frame.
            next_strip = None
            # Start searching from the strip *after* the current one in the global time-sorted list.
            for i in range(current_index_in_all + 1, len(all_strips_sorted_by_time)):
                potential_next = all_strips_sorted_by_time[i]

                # Check if the potential next strip is in the same channel
                # AND starts strictly after the current strip's *final* end frame.
                # (Using frame_final_end reflects the strip's current presence on the timeline)
                if potential_next.channel == current_strip.channel and \
                   potential_next.frame_start > current_strip.frame_final_end:
                    next_strip = potential_next
                    # Found the first chronological next strip in the same channel that starts *after* the current one ends.
                    break # Stop searching for this current_strip's successor.

            if next_strip:
                # Log details about the found next strip.
                print(f"  Found potential next strip in same channel: {next_strip.name} (Start: {next_strip.frame_start}, Channel: {next_strip.channel})")

                # Calculate the number of empty frames between the current strip's end and the next strip's start.
                # If strip A ends at frame 100 (frame_final_end=100) and strip B starts at frame 102 (frame_start=102),
                # the gap frames are frame 101, which is 1 frame.
                # Gap frames = next_strip.frame_start - (current_strip.frame_final_end + 1)
                num_gap_frames = next_strip.frame_start - (current_strip.frame_final_end + 1)

                print(f"  Current Strip End Frame (inclusive): {current_strip.frame_final_end}")
                print(f"  Next Strip Start Frame: {next_strip.frame_start}")
                print(f"  Calculated Gap (number of frames between): {num_gap_frames} frames")

                # Define the maximum gap allowed for extension.
                max_gap = 5000

                # Check the gap condition: must be positive (a gap exists) and within the maximum allowed range.
                # A positive number of gap frames means there's space.
                if num_gap_frames > 0 and num_gap_frames <= max_gap:
                    print(f"  Gap of {num_gap_frames} frames is within (0, {max_gap}] range. Extending strip.")

                    # The target end frame is the frame immediately before the next strip starts.
                    # Since frame_final_end is inclusive, setting it to `next_strip.frame_start - 1`
                    # will make the current strip end exactly one frame before the next one begins, filling the gap.
                    target_end_frame = next_strip.frame_start - 1

                    # *** Ensure the target end frame is an integer using rounding ***
                    # Even though frame_start and frame_final_end are typically integers,
                    # intermediate calculations or how Blender stores them internally might result in floats.
                    # We need a strict integer for frame_final_end.
                    target_end_frame_int = int(round(target_end_frame))

                    # Calculate the potential new duration. This should be >= 1 if target_end_frame_int >= current_strip.frame_start.
                    new_duration_potential = target_end_frame_int - current_strip.frame_start + 1

                    # Ensure the calculated new duration is valid (at least 1 frame)
                    # and that the target end frame is not before the strip's start.
                    if new_duration_potential > 0:
                        # --- Apply the new end frame ---

                        # Set the frame_final_end property. Blender handles duration and source offset adjustments internally
                        # when this property is set for common strip types (Movie, Image, Sound).
                        current_strip.frame_final_end = target_end_frame_int

                        # Log the successful extension details.
                        # Get the actual frame_final_end and duration after Blender updates them.
                        actual_new_end_frame = current_strip.frame_final_end
                        actual_new_duration = current_strip.frame_final_duration
                        print(f"  Successfully extended '{current_strip.name}' to end at frame {actual_new_end_frame}. New duration: {actual_new_duration}")
                        processed_count += 1
                    else:
                        # This case indicates an unexpected calculation resulting in an invalid target end frame or duration.
                         print(f"  Calculated target end frame {target_end_frame_int} results in non-positive duration. No change needed.")


                else:
                    # Log why the strip was not extended (gap is too large, zero, or negative/overlapping).
                    # Round the number of gap frames for cleaner logging output.
                    # Handle potentially very large gaps gracefully in logging.
                    log_gap = int(round(num_gap_frames)) if abs(num_gap_frames) < 2000 else num_gap_frames
                    print(f"  Calculated Gap {log_gap} frames is not within (0, {max_gap}] range or is not positive (overlapping/touching). No extension needed.")

            else:
                # Log if no subsequent strip was found in the same channel that starts AFTER the current strip ends.
                print(f"  No subsequent strip found in the same channel that starts after this one ends.")

        # Report the final summary using Blender's built-in reporting system (appears in the info bar).
        if processed_count > 0:
             self.report({'INFO'}, f"Script finished. Extended {processed_count} selected strip(s).")
        else:
             self.report({'INFO'}, "Script finished. No selected strips were extended.")

        # Print final summary to the console/system console as well.
        print(f"\nScript finished. Extended {processed_count} selected strip(s).")

        # Indicate that the operation finished successfully.
        return {'FINISHED'}

# Function to add the operator to the Strip -> Transform menu.
# 'self' here refers to the menu layout object provided by Blender.
def menu_func(self, context):
    # Add the operator button to the layout.
    self.layout.operator(SEQUENCER_OT_extend_to_next_strip.bl_idname, text=SEQUENCER_OT_extend_to_next_strip.bl_label)

# Register function for the add-on.
def register():
    # Register the operator class with Blender.
    bpy.utils.register_class(SEQUENCER_OT_extend_to_next_strip)
    # Append our custom menu function to the existing Strip -> Transform menu.
    bpy.types.SEQUENCER_MT_strip_transform.append(menu_func)
    print("VSE Extend Strips add-on registered.") # Optional: Print confirmation on register

# Unregister function for the add-on.
def unregister():
    # Remove our custom menu function from the Strip -> Transform menu.
    bpy.types.SEQUENCER_MT_strip_transform.remove(menu_func)
    # Unregister the operator class from Blender.
    bpy.utils.unregister_class(SEQUENCER_OT_extend_to_next_strip)
    print("VSE Extend Strips add-on unregistered.") # Optional: Print confirmation on unregister

# This block is executed only when the script is run directly in the text editor.
# It's useful for initial testing without installing the add-on fully.
if __name__ == "__main__":
    # Call the register function to make the operator available.
    register()
    # Optional: Automatically call the operator for immediate testing.
    # try:
    #     print("Attempting to run operator directly...")
    #     bpy.ops.sequencer.extend_to_next_strip()
    #     print("Operator finished.")
    # except Exception as e:
    #     print(f"Error during direct operator run: {e}")
    # finally:
    #     # Clean up by unregistering if you ran it directly
    #     unregister()
    #     print("Cleaned up registration from direct run.")
    pass # Keep the pass if you don't want to auto-run
