import os
import shutil
from typing import Any

import fitz  # PyMuPDF
from PIL import Image


class FileService:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.scan_folder = self.config_manager.get_setting("DocumentProcessing", "scan_folder")
        self.organized_folder = os.path.join(
            self.scan_folder,
            self.config_manager.get_setting("DocumentProcessing", "organized_subfolder"),
        )

        os.makedirs(self.scan_folder, exist_ok=True)
        os.makedirs(self.organized_folder, exist_ok=True)

    def _get_image_files(self) -> list[str]:
        """Scans the scan_folder for PNG and TIFF files."""
        image_files = []
        for f in os.listdir(self.scan_folder):
            file_path = os.path.join(self.scan_folder, f)
            if os.path.isfile(file_path):
                if f.lower().endswith(".png"):
                    image_files.append(file_path)
                elif f.lower().endswith((".tiff", ".tif")):
                    # Convert TIFF to PNG and then add to list
                    png_path = self._convert_tiff_to_png(file_path)
                    if png_path:
                        image_files.append(png_path)
        return image_files

    def _convert_tiff_to_png(self, tiff_path: str) -> str | None:
        """Converts a TIFF file to PNG and returns the new PNG path. Deletes original TIFF."""
        try:
            with Image.open(tiff_path) as img:
                png_path = os.path.splitext(tiff_path)[0] + ".png"
                img.save(png_path, "PNG")
            os.remove(tiff_path)  # Delete original TIFF after conversion
            return png_path
        except Exception as e:
            print(f"Error converting TIFF {tiff_path} to PNG: {e}")
            return None

    def group_files_by_timestamp(
        self, files: list[str], time_delta_seconds: int = 5
    ) -> list[list[str]]:
        """
        Groups files by their creation/modification timestamp, assuming consecutive scans.
        Files must be in chronological order for best results.
        """
        if not files:
            return []

        # Get file stats including creation/modification time
        file_data: list[dict[str, str | float]] = []
        for f in files:
            try:
                # Use st_mtime as it's often more reliable for 'last modified' by scanner
                m_time = os.path.getmtime(f)
                file_data.append({"path": f, "mtime": m_time})
            except Exception as e:
                print(f"Warning: Could not get mtime for {f}: {e}. Skipping file.")
                continue

        # Sort files by modification time
        file_data.sort(key=lambda x: float(x["mtime"]))

        grouped_files: list[list[str]] = []
        current_group: list[str] = []
        last_mtime: float | None = None

        for item in file_data:
            if not current_group:
                current_group.append(str(item["path"]))
                last_mtime = float(item["mtime"])
            else:
                if (float(item["mtime"]) - last_mtime) < time_delta_seconds:  # type: ignore[operator]
                    current_group.append(str(item["path"]))
                else:
                    grouped_files.append(current_group)
                    current_group = [str(item["path"])]
                last_mtime = float(item["mtime"])

        if current_group:
            grouped_files.append(current_group)

        return grouped_files

    def create_searchable_pdf(
        self,
        image_paths: list[str],
        output_filename: str,
        extracted_text_coords: dict[str, Any],
        is_searchable: bool = True,
        rotation_map: dict[str, int] | None = None,
    ) -> str | None:
        """
        Creates a PDF from a list of image paths, optionally adding a text layer for searchability.
        extracted_text_coords should be a dict like {"pages": [{"page_number": 1, "elements": [{"text": "...", "bbox": [...]}]}]}
        rotation_map: Optional dict mapping image_path -> rotation_degrees (Phase 8)
        """
        if not image_paths:
            return None

        if rotation_map is None:
            rotation_map = {}

        output_path = os.path.join(self.organized_folder, output_filename)
        doc = fitz.open()  # New PDF document

        for i, img_path in enumerate(image_paths):
            try:
                img_page_number = i + 1  # Assuming pages are ordered 1 to N

                # Create a new page the size of the image, ensuring file handle is closed
                with Image.open(img_path) as img:
                    # Phase 8: Apply rotation if specified (display-only rotation from database)
                    rotation_degrees = rotation_map.get(img_path, 0)
                    if rotation_degrees != 0:
                        # PIL rotation: positive = counter-clockwise, negative = clockwise
                        # For 90° CW, we rotate -90° (or 270° CCW)
                        if rotation_degrees == 90:
                            img = img.rotate(-90, expand=True)  # type: ignore[assignment]
                        elif rotation_degrees == 180:
                            img = img.rotate(180, expand=True)  # type: ignore[assignment]
                        elif rotation_degrees == 270:
                            img = img.rotate(90, expand=True)  # type: ignore[assignment]  # 270° CW = 90° CCW

                    img_rect = fitz.Rect(0, 0, img.width, img.height)

                page = doc.new_page(-1, width=img_rect.width, height=img_rect.height)

                # Phase 8: If rotation was applied, save rotated image to temp file and insert that
                if rotation_degrees != 0:
                    import tempfile

                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                        temp_path = temp_file.name
                        img.save(temp_path)
                    page.insert_image(img_rect, filename=temp_path)
                    os.remove(temp_path)  # Clean up temp file
                else:
                    # Add the image to the page (no rotation)
                    page.insert_image(img_rect, filename=img_path)

                if is_searchable and extracted_text_coords and "pages" in extracted_text_coords:
                    # Find the corresponding text/coords for this image_path's page number
                    page_coords = next(
                        (
                            p
                            for p in extracted_text_coords["pages"]
                            if p.get("page_number") == img_page_number
                        ),
                        None,
                    )

                    if page_coords and "elements" in page_coords:
                        for element in page_coords["elements"]:
                            text = element.get("text")
                            bbox = element.get("bbox")  # [x_min, y_min, x_max, y_max]
                            if text and bbox and len(bbox) == 4:
                                text_rect = fitz.Rect(bbox)
                                # Insert text with a transparent color
                                page.insert_textbox(
                                    text_rect,
                                    text,
                                    fontname="helv",  # Standard font
                                    fontsize=max(5, (text_rect.height * 0.8)),  # Estimate font size
                                    # Adjust color based on page background etc, but making it invisible
                                    # alpha=0 for fully invisible
                                    oc=0,
                                )  # oc=0 makes text invisible but searchable.
                                # An alternative might be fill=None, stroke=None, but oc is cleaner for searchability

                print(f"Added {img_path} to PDF.")
            except Exception as e:
                print(f"Error processing image {img_path} for PDF: {e}")
                # Decide if we want to fail the whole PDF or just skip the page
                # For now, print error and continue, will result in fewer pages

        if not doc.page_count:
            print("Warning: No pages were added to the PDF document.")
            return None

        doc.save(output_path)
        doc.close()
        print(f"PDF created: {output_path}")
        return output_path

    def delete_files(self, file_paths: list[str]):
        """Deletes a list of files."""
        for f_path in file_paths:
            try:
                os.remove(f_path)
                print(f"Deleted: {f_path}")
            except Exception as e:
                print(f"Error deleting file {f_path}: {e}")

    def move_pdf_to_organized(self, pdf_path: str, new_filename: str) -> str | None:
        """Moves the created PDF to the organized folder with the new filename."""
        final_path = os.path.join(self.organized_folder, new_filename)
        try:
            shutil.move(pdf_path, final_path)
            print(f"Moved PDF to {final_path}")
            return final_path
        except Exception as e:
            print(f"Error moving PDF {pdf_path} to {final_path}: {e}")
            return None
