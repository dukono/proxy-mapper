"""Profile Manager Dialog for managing WireMock profiles."""

from nicegui import ui

from config import get_global_config, WireMockProfile


class ProfileManagerDialog:
    """Dialog for managing WireMock profiles."""

    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.dialog = None
        self._profiles_list = None

    def show(self):
        """Show the profile manager dialog."""
        config = get_global_config()

        with ui.dialog() as self.dialog:
            ui.add_css('''
                .profile-manager-dialog > .q-dialog__inner {
                    max-width: none !important;
                    max-height: none !important;
                    padding: 0 !important;
                    pointer-events: none;
                }
                .profile-manager-card {
                    pointer-events: all;
                    position: fixed !important;
                    top: 50% !important;
                    left: 50% !important;
                    transform: translate(-50%, -50%) !important;
                    display: flex !important;
                    flex-direction: column !important;
                    resize: both;
                    overflow: hidden !important;
                    width: 620px;
                    min-width: 400px;
                    height: 500px;
                    min-height: 300px;
                }
                .profile-manager-card .profile-scroll {
                    flex: 1 !important;
                    min-height: 0 !important;
                    overflow-y: auto !important;
                }
            ''')
            self.dialog.classes('profile-manager-dialog')

            with ui.card().classes('bg-gray-800 p-0 profile-manager-card'):
                # Header
                with ui.row().classes('w-full px-4 py-3 border-b border-gray-700 items-center justify-between shrink-0'):
                    ui.label("Profile Manager").classes('text-xl font-bold text-white')
                    ui.button(icon='close', on_click=self.dialog.close).props('flat round dense').classes('text-gray-400')

                # Profiles list — plain scroll area
                with ui.element('div').classes('profile-scroll w-full').style('padding:12px 16px;'):
                    self._profiles_list = ui.column().classes('w-full gap-3')
                    self._render_profiles_list(config)

                # Footer
                with ui.row().classes('w-full px-4 py-3 border-t border-gray-700 justify-center shrink-0'):
                    ui.button('Add New Profile', on_click=self._show_add_profile, icon='add').classes('bg-blue-600 text-white')

        self.dialog.open()

    def _render_profiles_list(self, config):
        """Render the list of profiles."""
        self._profiles_list.clear()
        with self._profiles_list:
            if not config.profiles:
                ui.label("No profiles configured").classes('text-gray-500 text-center p-4')
                return

            for profile in config.profiles:
                try:
                    is_current = profile.name == config.current_profile
                    bg_color = 'bg-blue-900/40 border-blue-700' if is_current else 'bg-gray-700/60 border-gray-600'
                    mappings_dir = getattr(profile, 'mappings_path', '') or (profile.root_path + '/mappings')

                    with ui.card().classes(f'w-full p-3 border {bg_color}').style('min-width:0; overflow:hidden;'):
                        with ui.row().classes('w-full items-start justify-between gap-2').style('min-width:0;'):
                            # Info column — truncate long paths
                            with ui.column().classes('gap-0.5').style('min-width:0; flex:1; overflow:hidden;'):
                                with ui.row().classes('items-center gap-2 flex-wrap'):
                                    ui.label(profile.name).classes('text-white font-bold text-sm')
                                    if is_current:
                                        ui.label('Active').classes('text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded')
                                    ui.label(profile.mapping_type).classes('text-xs bg-gray-600 text-gray-200 px-1.5 py-0.5 rounded')
                                if profile.description:
                                    ui.label(profile.description).classes('text-gray-400 text-xs')
                                ui.label(mappings_dir).classes('text-gray-500 text-xs font-mono').style(
                                    'white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%;'
                                ).tooltip(mappings_dir)
                                if getattr(profile, 'service_url', '') and profile.mapping_type == 'Wire':
                                    ui.label(profile.service_url).classes('text-blue-400 text-xs font-mono').style(
                                        'white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%;'
                                    ).tooltip(profile.service_url)

                            # Action buttons — fixed width, no shrink
                            with ui.row().classes('gap-1 items-center shrink-0'):
                                if not is_current:
                                    ui.button(
                                        'Activate',
                                        on_click=lambda p=profile: self._activate_profile(p.name)
                                    ).props('flat dense size=sm color=green').classes('text-xs')
                                ui.button(
                                    icon='edit',
                                    on_click=lambda p=profile: self._edit_profile(p)
                                ).props('flat round dense color=blue size=sm')
                                if len(config.profiles) > 1:
                                    ui.button(
                                        icon='delete',
                                        on_click=lambda p=profile: self._delete_profile(p.name)
                                    ).props('flat round dense color=red size=sm')
                except Exception as exc:
                    ui.label(f"Error: {exc}").classes('text-red-400 text-xs p-2')

    def _activate_profile(self, name: str):
        """Activate a profile."""
        config = get_global_config()
        config.set_current_profile(name)
        ui.notify(f"Activated profile: {name}", type='positive')

        # Update profile select if exists
        if hasattr(self.ui, 'profile_select'):
            self.ui.profile_select.set_value(name)

        # Reload mappings
        if hasattr(self.ui, '_auto_load_mappings'):
            from config.globals import set_mappings_loaded
            set_mappings_loaded(False)   # force reload for the new profile
            self.ui._auto_load_mappings()

        # Refresh mappings view if available
        if hasattr(self.ui, 'mappings_view') and hasattr(self.ui.mappings_view, 'refresh'):
            self.ui.mappings_view.refresh()

        # Refresh dialog
        self._render_profiles_list(config)

    def _show_add_profile(self):
        """Show dialog to add a new profile."""
        with ui.dialog() as add_dialog:
            with ui.card().classes('bg-gray-800 p-4').style(
                'width:500px; min-width:350px; min-height:300px; resize:both; overflow:auto;'
            ):
                ui.label("Add New Profile").classes('text-lg font-bold text-white mb-4')

                name_input = ui.input(label='Profile Name', placeholder='e.g., Production').classes('w-full').props('dark outlined')
                desc_input = ui.input(label='Description', placeholder='Optional description').classes('w-full').props('dark outlined')

                ui.label("Mapping Type").classes('text-xs text-gray-400 mt-2')
                type_select = ui.select(
                    options=['Wire', 'default'],
                    value='Wire'
                ).classes('w-full').props('dark outlined')

                path_input = ui.input(
                    label='Mappings Directory Path',
                    placeholder='/absolute/path/to/mappings'
                ).classes('w-full').props('dark outlined')

                url_row = ui.column().classes('w-full')
                with url_row:
                    url_input = ui.input(
                        label='Service URL (Wire type only)',
                        placeholder='http://wiremock:8080'
                    ).classes('w-full').props('dark outlined')

                def _on_type_change(e):
                    url_row.set_visibility(e.value == 'Wire')

                type_select.on_value_change(_on_type_change)

                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=add_dialog.close).props('flat color=white')
                    ui.button(
                        'Create',
                        on_click=lambda: self._create_profile(
                            name_input.value,
                            desc_input.value,
                            type_select.value,
                            url_input.value,
                            path_input.value,
                            add_dialog
                        )
                    ).classes('bg-green-600 text-white')

        add_dialog.open()

    def _create_profile(self, name: str, description: str, mapping_type: str, service_url: str, mappings_path: str, dialog):
        """Create a new profile."""
        if not name:
            ui.notify("Profile name is required", type='negative')
            return
        if not mappings_path:
            ui.notify("Mappings directory path is required", type='negative')
            return

        config = get_global_config()
        # Check if name already exists
        if config.get_profile(name):
            ui.notify(f"Profile '{name}' already exists", type='negative')
            return

        # Create default root path based on name
        import os
        root_path = os.path.dirname(mappings_path) if mappings_path else os.path.join(os.path.dirname(__file__), '..', f'wiremock_{name.lower().replace(" ", "_")}')

        profile = WireMockProfile(
            name=name,
            root_path=root_path,
            description=description,
            mapping_type=mapping_type,
            service_url=service_url if mapping_type == 'Wire' else '',
            mappings_path=mappings_path,
        )

        config.add_profile(profile)
        config.set_current_profile(name)

        ui.notify(f"Created profile: {name}", type='positive')
        dialog.close()
        self._render_profiles_list(config)

    def _edit_profile(self, profile):
        """Show dialog to edit a profile."""
        with ui.dialog() as edit_dialog:
            with ui.card().classes('bg-gray-800 p-4').style(
                'width:500px; min-width:350px; min-height:300px; resize:both; overflow:auto;'
            ):
                ui.label(f"Edit Profile: {profile.name}").classes('text-lg font-bold text-white mb-4')

                desc_input = ui.input(
                    label='Description',
                    value=profile.description
                ).classes('w-full').props('dark outlined')

                ui.label("Mapping Type").classes('text-xs text-gray-400 mt-2')
                type_select = ui.select(
                    options=['Wire', 'default'],
                    value=profile.mapping_type
                ).classes('w-full').props('dark outlined')

                path_input = ui.input(
                    label='Mappings Directory Path',
                    value=profile.mappings_path or '',
                    placeholder='/absolute/path/to/mappings'
                ).classes('w-full').props('dark outlined')

                url_row = ui.column().classes('w-full')
                with url_row:
                    url_input = ui.input(
                        label='Service URL (Wire type only)',
                        value=profile.service_url
                    ).classes('w-full').props('dark outlined')
                url_row.set_visibility(profile.mapping_type == 'Wire')

                def _on_type_change(e):
                    url_row.set_visibility(e.value == 'Wire')

                type_select.on_value_change(_on_type_change)

                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=edit_dialog.close).props('flat color=white')
                    ui.button(
                        'Save',
                        on_click=lambda: self._update_profile(
                            profile.name,
                            desc_input.value,
                            type_select.value,
                            url_input.value,
                            path_input.value,
                            edit_dialog
                        )
                    ).classes('bg-green-600 text-white')

        edit_dialog.open()

    def _update_profile(self, name: str, description: str, mapping_type: str, service_url: str, mappings_path: str, dialog):
        """Update an existing profile."""
        config = get_global_config()
        profile = config.get_profile(name)

        if profile:
            profile.description = description
            profile.mapping_type = mapping_type
            profile.service_url = service_url if mapping_type == 'Wire' else ''
            profile.mappings_path = mappings_path
            if mappings_path:
                import os
                profile.root_path = os.path.dirname(mappings_path)
            config._save_config()

            ui.notify(f"Updated profile: {name}", type='positive')
            dialog.close()
            self._render_profiles_list(config)

            # Reload mappings if current profile
            if config.current_profile == name:
                if hasattr(self.ui, '_auto_load_mappings'):
                    from config.globals import set_mappings_loaded
                    set_mappings_loaded(False)
                    self.ui._auto_load_mappings()
                # Refresh mappings view if available
                if hasattr(self.ui, 'mappings_view') and hasattr(self.ui.mappings_view, 'refresh'):
                    self.ui.mappings_view.refresh()

    def _delete_profile(self, name: str):
        """Delete a profile."""
        config = get_global_config()

        if config.current_profile == name and len(config.profiles) <= 1:
            ui.notify("Cannot delete the last active profile", type='negative')
            return

        config.remove_profile(name)
        ui.notify(f"Deleted profile: {name}", type='positive')
        self._render_profiles_list(config)
