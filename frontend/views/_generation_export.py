# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Export mixin for GenerationMethodScreen — Excel generation and print tracking."""

import os
import sys
import threading
from datetime import datetime
from tkinter import messagebox

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from backend.services.bracket_excel_generator import BracketExcelGenerator  # noqa: E402
from backend.services.pool_excel_generator import PoolExcelGenerator  # noqa: E402
from ..utils.pool_renderer import split_into_pools  # noqa: E402


class _ExportMixin:
    """Mixin for Excel export and print tracking logic."""

    def on_print_selected(self):
        """Generate Excel for the currently selected bracket only."""
        selected_bracket = self.selected_unassigned or (
            self.selected_in_tables.get(self.METHOD_POOLS) or
            self.selected_in_tables.get(self.METHOD_DOUBLE) or
            self.selected_in_tables.get(self.METHOD_KO) or
            self.selected_in_tables.get(self.METHOD_SPECIAL)
        )

        if not selected_bracket:
            self.logger.debug("Print selected action failed: no bracket selected")
            messagebox.showwarning("Warning", "Please select a bracket to print")
            return

        bracket_data = self.brackets.get(selected_bracket)
        if not bracket_data:
            self.logger.error(f"Bracket not found: {selected_bracket}")
            messagebox.showerror("Error", f"Bracket data not found: {selected_bracket}")
            return

        method = bracket_data.get("method")
        if not method:
            self.logger.warning(f"Bracket has no assigned method: {selected_bracket}")
            messagebox.showwarning("Warning", "Please assign a method before printing")
            return

        if selected_bracket in self.printed_brackets:
            printed_time = self.printed_brackets[selected_bracket].strftime("%Y-%m-%d %H:%M:%S")
            result = messagebox.askyesno(
                "Already Printed",
                f"This bracket was printed on {printed_time}.\nPrint again?",
            )
            if not result:
                self.logger.info(f"User cancelled reprint of: {selected_bracket}")
                return
            self.logger.info(f"User approved reprint of: {selected_bracket}")

        if self.main_window and hasattr(self.main_window, 'task_runner'):
            self.main_window.task_runner.submit_task(
                'export_bracket',
                fn=lambda on_progress=None: self._excel_export_worker_fn([selected_bracket], on_progress),
                on_progress=self._on_export_progress,
                on_error=self._on_export_error,
                on_complete=self._on_export_complete,
            )
            self.logger.info(f"Export task submitted to TaskRunner for: {selected_bracket}")
        else:
            self.logger.warning("TaskRunner not available, falling back to direct threading")
            thread = threading.Thread(
                target=self._excel_export_worker,
                args=([selected_bracket],),
                daemon=True,
            )
            thread.start()

    def on_export_all(self):
        """Generate Excel files for all currently assigned brackets."""
        assigned_brackets = [
            k for k, v in self.brackets.items()
            if v.get("method") is not None and len(v.get("tuple", [])) > 0
        ]

        if not assigned_brackets:
            self.logger.info("Export all action: no assigned brackets to export")
            messagebox.showinfo("Info", "No assigned brackets to export")
            return

        self.logger.info(f"Exporting {len(assigned_brackets)} assigned brackets via TaskRunner")

        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.show_loading_progress(
                f"Exporting {len(assigned_brackets)} brackets..."
            )

        if self.main_window and hasattr(self.main_window, 'task_runner'):
            self.main_window.task_runner.submit_task(
                'export_all_brackets',
                fn=lambda on_progress=None: self._excel_export_worker_fn(assigned_brackets, on_progress),
                on_progress=self._on_export_progress,
                on_error=self._on_export_error,
                on_complete=self._on_export_complete,
            )
            self.logger.info(f"Export all task submitted to TaskRunner for {len(assigned_brackets)} brackets")
        else:
            self.logger.warning("TaskRunner not available, falling back to direct threading")
            thread = threading.Thread(
                target=self._excel_export_worker,
                args=(assigned_brackets,),
                daemon=True,
            )
            thread.start()

    def _excel_export_worker_fn(self, bracket_keys, on_progress=None):
        """
        TaskRunner-compatible worker function for Excel exports.

        Returns:
            Dictionary with export results: {'success': int, 'reprint': int, 'failed': int, 'errors': []}
        """
        try:
            self._create_export_directory()

            success_count = 0
            reprint_count = 0
            error_count = 0
            errors = []
            total = len(bracket_keys)

            for idx, bracket_key in enumerate(bracket_keys):
                try:
                    if bracket_key not in self.brackets:
                        self.logger.warning(f"Bracket not found during export: {bracket_key}")
                        error_count += 1
                        errors.append(f"{bracket_key}: Bracket data not found")
                        continue

                    bracket_data = self.brackets[bracket_key]
                    fighters = bracket_data.get("tuple", [])
                    method = bracket_data.get("method")

                    if not fighters or len(fighters) == 0:
                        self.logger.debug(f"Skipping empty bracket: {bracket_key}")
                        continue

                    if not method:
                        self.logger.warning(f"Bracket has no method assigned: {bracket_key}")
                        error_count += 1
                        errors.append(f"{bracket_key}: No method assigned")
                        continue

                    is_reprint = bracket_key in self.printed_brackets
                    success = self._export_bracket_to_excel(bracket_key, method, fighters)

                    if success:
                        self._mark_bracket_printed(bracket_key)
                        if is_reprint:
                            reprint_count += 1
                            self.logger.info(f"[REPRINT] {bracket_key} ({method})")
                        else:
                            success_count += 1
                            self.logger.info(f"[EXPORT] {bracket_key} ({method})")
                    else:
                        error_count += 1
                        errors.append(f"{bracket_key}: Export failed")
                        self.logger.error(f"Failed to export {bracket_key}")

                except Exception as e:
                    error_count += 1
                    errors.append(f"{bracket_key}: {str(e)}")
                    self.logger.error(f"Error exporting {bracket_key}: {e}", exc_info=True)

                if on_progress:
                    on_progress(int((idx + 1) / total * 100))

            result = {
                'success': success_count,
                'reprint': reprint_count,
                'failed': error_count,
                'errors': errors,
            }
            self.logger.info(f"Export worker completed: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Excel export worker failed: {e}", exc_info=True)
            raise

    def _on_export_progress(self, progress_value):
        """Called when export progress is updated (0-100)."""
        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.update_progress(progress_value)
            self.logger.debug(f"Export progress: {progress_value}%")

    def _on_export_error(self, error):
        """Called when export task encounters an error."""
        error_msg = str(error)
        self.logger.error(f"Export task error: {error_msg}")

        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.hide_loading_progress()
            self.main_window.ui_feedback.show_error("Export Error", error_msg)

    def _on_export_complete(self, result):
        """Called when export task completes successfully."""
        success_count = result.get('success', 0)
        reprint_count = result.get('reprint', 0)
        error_count = result.get('failed', 0)
        errors = result.get('errors', [])

        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.hide_loading_progress()

        summary_lines = []
        if success_count > 0:
            summary_lines.append(f"✓ Exported {success_count} bracket(s)")
        if reprint_count > 0:
            summary_lines.append(f"↻ Reprinted {reprint_count} bracket(s)")
        if error_count > 0:
            summary_lines.append(f"✗ Failed {error_count} bracket(s)")

        summary_text = "\n".join(summary_lines)
        if error_count > 0:
            summary_text += "\n\nErrors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                summary_text += f"\n... and {len(errors) - 5} more"

        summary_text += "\n\nFiles saved to:\n/temp/exports/"

        self.logger.info(f"Export completed: {summary_text.replace(chr(10), ' | ')}")
        messagebox.showinfo("Export Complete", summary_text)

    def _excel_export_worker(self, bracket_keys):
        """
        Background worker fallback for Excel export (used when TaskRunner is not available).
        """
        try:
            result = self._excel_export_worker_fn(bracket_keys, on_progress=None)
            self.master.after(0, lambda r=result: self._on_export_complete(r))
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Excel export worker failed: {e}", exc_info=True)
            self.master.after(0, lambda msg=error_msg: messagebox.showerror("Export Error", msg))

    def _export_bracket_to_excel(self, bracket_key, method, fighters):
        """Generate Excel file for a single bracket."""
        try:
            filename = self._sanitize_filename(bracket_key, method)
            output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'temp', 'exports', filename)
            output_path = os.path.abspath(output_path)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self.logger.debug(f"Exporting to: {output_path}")

            if method == self.METHOD_POOLS:
                pools_data = [{'pool_name': bracket_key, 'fighters': fighters}]
                generator = PoolExcelGenerator()
                success = generator.generate_pools_excel(
                    output_path=output_path,
                    pools_data=pools_data,
                    title=bracket_key,
                    include_finale=False,
                )
            elif method == self.METHOD_DOUBLE:
                pools = split_into_pools(fighters, num_pools=2)
                pools_data = [
                    {'pool_name': f"{bracket_key} - Pool {i+1}", 'fighters': pool}
                    for i, pool in enumerate(pools)
                ]
                generator = PoolExcelGenerator()
                success = generator.generate_pools_excel(
                    output_path=output_path,
                    pools_data=pools_data,
                    title=bracket_key,
                    include_finale=True,
                )
            else:
                generator = BracketExcelGenerator()
                success = generator.generate_bracket_excel(
                    output_path=output_path,
                    fighters=fighters,
                    bracket_type='double',
                    title=bracket_key,
                )

            if success:
                self.logger.info(f"Successfully exported: {bracket_key} → {output_path}")
            else:
                self.logger.error(f"Generator returned False for: {bracket_key}")

            return success

        except Exception as e:
            self.logger.error(f"Error exporting bracket {bracket_key}: {e}", exc_info=True)
            return False

    def _mark_bracket_printed(self, bracket_key):
        """Mark a bracket as printed and update display."""
        self.printed_brackets[bracket_key] = datetime.now()
        self.logger.info(f"Marked as printed: {bracket_key}")
        self._refresh_all_displays()

    def _sanitize_filename(self, bracket_key, method):
        """Convert bracket key to a safe filename."""
        safe_key = bracket_key.replace('|', '').replace('/', '_').replace('\\', '_').strip()
        safe_key = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in safe_key)
        safe_key = '_'.join(safe_key.split())
        method_name = method.upper() if method else 'UNKNOWN'
        return f"{safe_key}_{method_name}.xlsx"

    def _create_export_directory(self):
        """Ensure /temp/exports/ directory exists."""
        export_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'temp', 'exports')
        export_dir = os.path.abspath(export_dir)
        os.makedirs(export_dir, exist_ok=True)
        self.logger.debug(f"Export directory ready: {export_dir}")
