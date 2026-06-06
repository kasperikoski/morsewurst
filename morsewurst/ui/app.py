from __future__ import annotations

import tkinter as tk

from morsewurst.i18n import I18nService
from morsewurst.ui.controllers import (
    AppLifecycleController,
    AudioController,
    BackupController,
    ChallengeSettingsController,
    DebugController,
    DecoderController,
    EffectiveWpmController,
    HistoryController,
    InputController,
    KochController,
    LayoutController,
    PracticeController,
    ProfileController,
    ResultsController,
    RuntimeController,
    SerialController,
    SettingsController,
    StartupController,
    StartupSequenceController,
    StatusController,
    UiHelpersController,
    UpdateController,
    WindowController,
    WxmorController,
)


class MorsewurstApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.i18n = I18nService()

        self.window_controller = WindowController(self)
        self.app_lifecycle_controller = AppLifecycleController(self)
        self.debug_controller = DebugController(self)
        self.decoder_controller = DecoderController(self)
        self.effective_wpm_controller = EffectiveWpmController(self)
        self.profile_controller = ProfileController(self)
        self.settings_controller = SettingsController(self)
        self.challenge_settings_controller = ChallengeSettingsController(self)
        self.ui_helpers_controller = UiHelpersController(self)
        self.startup_controller = StartupController(self)
        self.startup_sequence_controller = StartupSequenceController(self)
        self.input_controller = InputController(self)
        self.koch_controller = KochController(self)
        self.layout_controller = LayoutController(self)
        self.serial_controller = SerialController(self)
        self.practice_controller = PracticeController(self)
        self.results_controller = ResultsController(self)
        self.history_controller = HistoryController(self)
        self.audio_controller = AudioController(self)
        self.backup_controller = BackupController(self)
        self.status_controller = StatusController(self)
        self.update_controller = UpdateController(self)
        self.wxmor_controller = WxmorController(self)
        self.runtime_controller = RuntimeController(self)

        self.startup_sequence_controller.run_startup()