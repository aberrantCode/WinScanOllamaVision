"""
Phase 7 Handler Methods for ConvertImagesWindow
These methods will be added to the ConvertImagesWindow class
"""

# Add these methods to ConvertImagesWindow class:

def _load_and_show_bundle_suggestions(self):
    """Generate and display bundle suggestions"""
    try:
        # Hide regular workflow UI
        self.content_layout.parentWidget().setVisible(False)
        self.thumbnail_scroll.setVisible(False)

        # Update step indicator
        self.step_title_label.setText("AI Bundle Suggestions")
        self.step_indicator_label.setText("Step 0 of 5")

        # Generate bundle suggestions using BundlingService
        bundles = self.bundling_service.generate_bundle_recommendations()

        if bundles and len(bundles) > 0:
            # Show bundle suggestions view
            self.bundle_suggestions_view.set_bundles(bundles)
            self.bundle_suggestions_view.setVisible(True)
            print(f"[Bundle Suggestions] Showing {len(bundles)} suggestions")
        else:
            # No bundles found, skip to manual workflow
            print("[Bundle Suggestions] No bundles generated, skipping to manual workflow")
            self._on_skip_to_manual_workflow()

    except Exception as e:
        print(f"[Bundle Suggestions] Error generating suggestions: {e}")
        import traceback
        traceback.print_exc()
        # Fall back to manual workflow
        self._on_skip_to_manual_workflow()


def _on_bundle_accepted(self, bundle_data):
    """Handle bundle acceptance"""
    print(f"[Bundle] Accepted: {bundle_data.get('document_type')} - {bundle_data.get('company')}")

    # Add to completed groups
    file_paths = bundle_data.get('file_paths', [])
    if file_paths:
        self.completed_groups.append(file_paths)

        # Store metadata
        group_key = f"group_{len(self.completed_groups)}"
        self.extracted_metadata[group_key] = {
            'company': bundle_data.get('company'),
            'title': bundle_data.get('document_type'),
            'date': bundle_data.get('document_date')
        }

        # Remove accepted bundle from view
        # (Bundles will be regenerated when view refreshes)
        QMessageBox.information(
            self,
            "Bundle Accepted",
            f"Accepted {len(file_paths)} page(s) for '{bundle_data.get('document_type')}'.\n\n"
            "This group will skip manual stitching and move directly to finalization."
        )


def _on_bundle_modified(self, bundle_data):
    """Handle bundle modification request"""
    print(f"[Bundle] Modify requested: {bundle_data.get('document_type')}")

    # Load the bundle files into the stitching workflow
    file_paths = bundle_data.get('file_paths', [])
    if file_paths:
        # Transition to stitching step with these files pre-loaded
        self.all_files = file_paths
        self.current_file_index = 0
        self.current_group = list(file_paths)  # Pre-select all files

        # Store suggested metadata for pre-population
        self.extracted_metadata['suggestion'] = {
            'company': bundle_data.get('company'),
            'title': bundle_data.get('document_type'),
            'date': bundle_data.get('document_date')
        }

        # Move to stitching step
        self.current_step = WorkflowStep.STITCHING
        self._transition_to_stitching()


def _on_bundle_rejected(self, bundle_data):
    """Handle bundle rejection"""
    print(f"[Bundle] Rejected: {bundle_data.get('document_type')}")

    # Mark files as excluded/rejected (optional - could add to a reject list)
    # For now, just remove from suggestions
    QMessageBox.information(
        self,
            "Bundle Rejected",
        f"Rejected bundle for '{bundle_data.get('document_type')}'.\n\n"
        "These pages will remain available for manual processing."
    )


def _on_accept_all_high_confidence(self):
    """Accept all high confidence bundles automatically"""
    high_confidence_bundles = self.bundle_suggestions_view.get_high_confidence_bundles()

    if not high_confidence_bundles:
        QMessageBox.information(
            self,
            "No High Confidence Bundles",
            "There are no high confidence bundles (>= 80%) to accept automatically."
        )
        return

    from PyQt6.QtWidgets import QMessageBox
    reply = QMessageBox.question(
        self,
        "Accept All High Confidence",
        f"Accept {len(high_confidence_bundles)} high confidence bundle(s) automatically?\n\n"
        "These documents will skip manual stitching and move directly to finalization.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if reply == QMessageBox.StandardButton.Yes:
        for bundle in high_confidence_bundles:
            file_paths = bundle.get('file_paths', [])
            if file_paths:
                self.completed_groups.append(file_paths)

                # Store metadata
                group_key = f"group_{len(self.completed_groups)}"
                self.extracted_metadata[group_key] = {
                    'company': bundle.get('company'),
                    'title': bundle.get('document_type'),
                    'date': bundle.get('document_date')
                }

        QMessageBox.information(
            self,
            "Bundles Accepted",
            f"Accepted {len(high_confidence_bundles)} high confidence bundle(s).\n\n"
            "You can now process remaining pages manually or skip to finalization."
        )

        # Check if there are remaining pages to process
        self._check_remaining_pages_after_bundles()


def _on_skip_to_manual_workflow(self):
    """Skip bundle suggestions and go to manual stitching"""
    print("[Bundle] Skipping to manual workflow")

    # Hide bundle suggestions
    self.bundle_suggestions_view.setVisible(False)

    # Show regular workflow UI
    self.content_layout.parentWidget().setVisible(True)
    self.thumbnail_scroll.setVisible(True)

    # Transition to stitching step
    self.current_step = WorkflowStep.STITCHING
    self._transition_to_stitching()


def _transition_to_stitching(self):
    """Transition from bundle suggestions to stitching step"""
    # Update UI for stitching step
    self.step_title_label.setText("Document Stitching")
    self.step_indicator_label.setText("Step 1 of 4")

    # Load files if not already loaded
    if not self.all_files:
        self._prompt_for_files()

    # Show first page
    if self.all_files:
        self._show_page(self.current_file_index)


def _check_remaining_pages_after_bundles(self):
    """Check if there are pages left to process after accepting bundles"""
    # Get all pages that were bundled
    bundled_files = set()
    for group in self.completed_groups:
        bundled_files.update(group)

    # Check if all files were bundled
    remaining_files = [f for f in self.all_files if f not in bundled_files]

    if remaining_files:
        reply = QMessageBox.question(
            self,
            "Remaining Pages",
            f"There are {len(remaining_files)} page(s) remaining that were not bundled.\n\n"
            "Would you like to process them manually?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Load remaining files for manual processing
            self.all_files = remaining_files
            self.current_file_index = 0
            self._on_skip_to_manual_workflow()
        else:
            # Skip to finalization
            self.current_step = WorkflowStep.FINALIZATION
            self._show_finalization_step()
    else:
        # All pages bundled, go to finalization
        QMessageBox.information(
            self,
            "All Pages Bundled",
            "All pages have been bundled! Proceeding to finalization."
        )
        self.current_step = WorkflowStep.FINALIZATION
        self._show_finalization_step()


def _show_finalization_step(self):
    """Show the finalization step"""
    # This method should already exist in ConvertImagesWindow
    # If not, we need to implement it
    # For now, just update the step indicator
    self.step_title_label.setText("Document Finalization")
    self.step_indicator_label.setText("Step 4 of 4")
    # TODO: Show finalization UI
