#Copyright (C) 2014, 4lCapwn and CS2001
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>


# Embedded file name: scripts/client/gui/Scaleform/daapi/view/lobby/settings/SettingsWindow.py
import functools
import BigWorld
import VOIP
import SoundGroups
from debug_utils import *
from gui.Scaleform.framework.entities.abstract.AbstractWindowView import AbstractWindowView
from gui.Scaleform.locale.SETTINGS import SETTINGS
from helpers import i18n
from Vibroeffects import VibroManager
from gui import DialogsInterface, g_guiResetters
from gui.BattleContext import g_battleContext
from gui.shared.utils import flashObject2Dict, decorators
from gui.Scaleform.daapi import AppRef
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.daapi.view.meta.SettingsWindowMeta import SettingsWindowMeta
from gui.Scaleform.daapi.view.lobby.settings.SettingsParams import SettingsParams
from account_helpers.settings_core import settings_constants
from account_helpers.settings_core.SettingsCore import g_settingsCore
from account_helpers.settings_core.options import APPLY_METHOD

# Own imports
import json
import urllib2
import threading
import os
import helpers
from gui import SystemMessages, VERSION_FILE_PATH


# Modified Methods are marked with *

class SettingsWindow(View, AbstractWindowView, SettingsWindowMeta, AppRef):

    def __init__(self, ctx):
        super(SettingsWindow, self).__init__()
        self.__redefinedKeyModeEnabled = ctx.get('redefinedKeyMode', True)
        self.__initialTabIdx = ctx.get('tabIndex', -1)
        self.params = SettingsParams()

    # *
    def __getSettings(self):
        return {'GameSettings': self.params.getGameSettings(),
         'GraphicSettings': self.params.getGraphicsSettings(),
         'SoundSettings': self.params.getSoundSettings(),
         'ControlsSettings': self.params.getControlsSettings(),
         'AimSettings': self.params.getAimSettings(),
         'MarkerSettings': self.params.getMarkersSettings(),
         'OtherSettings': self.params.getOtherSettings()
         }

    def __commitSettings(self, settings = None, restartApproved = False, isCloseWnd = False):
        if settings is None:
            settings = {}
        self.__apply(settings, restartApproved, isCloseWnd)
        return

    def __apply(self, settings, restartApproved = False, isCloseWnd = False):
        LOG_DEBUG('Settings window: apply settings', restartApproved, settings)
        g_settingsCore.isDeviseRecreated = False
        g_settingsCore.isChangesConfirmed = True
        isRestart = self.params.apply(settings, restartApproved)
        if g_settingsCore.isChangesConfirmed and isCloseWnd:
            self.onWindowClose()
        if isRestart:
            BigWorld.savePreferences()
            if restartApproved:
                BigWorld.callback(0.3, self.__restartGame)
            elif g_settingsCore.isDeviseRecreated:
                self.onRecreateDevice()
                g_settingsCore.isDeviseRecreated = False
            else:
                BigWorld.callback(0.0, functools.partial(BigWorld.changeVideoMode, -1, BigWorld.isVideoWindowed()))

    def __restartGame(self):
        BigWorld.savePreferences()
        BigWorld.restartGame()

    def _populate(self):
        super(SettingsWindow, self)._populate()
        self.__currentSettings = self.params.getMonitorSettings()
        self._update()
        VibroManager.g_instance.onConnect += self.onVibroManagerConnect
        VibroManager.g_instance.onDisconnect += self.onVibroManagerDisconnect
        g_guiResetters.add(self.onRecreateDevice)
        BigWorld.wg_setAdapterOrdinalNotifyCallback(self.onRecreateDevice)
        SoundGroups.g_instance.enableVoiceSounds(True)

    def _update(self):
        #print "SWPYTHON SENDING DICT"
        #print self.__getSettings()['ModSettings']
        self.as_setDataS(self.__getSettings())
        self.as_updateVideoSettingsS(self.__currentSettings)
        self.as_openTabS(self.__initialTabIdx)

    def _dispose(self):
        if not g_battleContext.isInBattle:
            SoundGroups.g_instance.enableVoiceSounds(False)
        g_guiResetters.discard(self.onRecreateDevice)
        BigWorld.wg_setAdapterOrdinalNotifyCallback(None)
        VibroManager.g_instance.onConnect -= self.onVibroManagerConnect
        VibroManager.g_instance.onDisconnect -= self.onVibroManagerDisconnect
        super(SettingsWindow, self)._dispose()
        return

    def onVibroManagerConnect(self):
        self.as_onVibroManagerConnectS(True)

    def onVibroManagerDisconnect(self):
        self.as_onVibroManagerConnectS(False)

    def onTabSelected(self, tabId):
        if tabId == SETTINGS.SOUNDTITLE:
            self.app.voiceChatManager.checkForInitialization()

    def onSettingsChange(self, settingName, settingValue):
        settingValue = flashObject2Dict(settingValue)
        self.params.preview(settingName, settingValue)

    def applySettings(self, settings, isCloseWnd):
        self._applySettings(flashObject2Dict(settings), isCloseWnd)

    def _applySettings(self, settings, isCloseWnd):
        applyMethod = self.params.getApplyMethod(settings)

        def confirmHandler(isOk):
            self.as_ConfirmationOfApplicationS(isOk)
            if isOk:
                self.__commitSettings(settings, isOk, isCloseWnd)
            else:
                self.params.revert()
                self._update()

        if applyMethod == APPLY_METHOD.RESTART:
            DialogsInterface.showI18nConfirmDialog('graphicsPresetRestartConfirmation', confirmHandler)
        elif applyMethod == APPLY_METHOD.DELAYED:
            DialogsInterface.showI18nConfirmDialog('graphicsPresetDelayedConfirmation', confirmHandler)
        else:
            confirmHandler(True)

    def onWindowClose(self):
        self.params.revert()
        self.startVOIPTest(False)
        self.destroy()

    def onRecreateDevice(self):
        actualSettings = self.params.getMonitorSettings()
        if self.__currentSettings and self.__currentSettings != actualSettings:
            curDrr = self.__currentSettings[settings_constants.GRAPHICS.DYNAMIC_RENDERER]
            actualDrr = actualSettings[settings_constants.GRAPHICS.DYNAMIC_RENDERER]
            self.__currentSettings = actualSettings
            result = self.__currentSettings.copy()
            if curDrr == actualDrr:
                result[settings_constants.GRAPHICS.DYNAMIC_RENDERER] = None
            self.as_updateVideoSettingsS(result)
        return

    def useRedifineKeysMode(self, isUse):
        if self.__redefinedKeyModeEnabled:
            BigWorld.wg_setRedefineKeysMode(isUse)

    def autodetectQuality(self):
        result = BigWorld.autoDetectGraphicsSettings()
        self.onRecreateDevice()
        return result

    def startVOIPTest(self, isStart):
        LOG_DEBUG('Vivox test: %s' % str(isStart))
        rh = VOIP.getVOIPManager()
        rh.enterTestChannel() if isStart else rh.leaveTestChannel()
        return False

    @decorators.process('__updateCaptureDevices')
    def updateCaptureDevices(self):
        yield self.app.voiceChatManager.requestCaptureDevices()
        opt = g_settingsCore.options.getSetting(settings_constants.SOUND.CAPTURE_DEVICES)
        self.as_setCaptureDevicesS(opt.get(), opt.getOptions())

    def altVoicesPreview(self):
        setting = self.params.SETTINGS.getSetting(settings_constants.SOUND.ALT_VOICES)
        if setting is not None:
            setting.playPreviewSound()
        return

    def isSoundModeValid(self):
        setting = self.params.SETTINGS.getSetting(settings_constants.SOUND.ALT_VOICES)
        if setting is not None:
            return setting.isSoundModeValid()
        else:
            return False

    def showWarningDialog(self, dialogID, settings, isCloseWnd):

        def callback(isOk):
            if isOk:
                self.applySettings(settings, False)
            self.as_confirmWarningDialogS(isOk, dialogID)
            if isCloseWnd and isOk:
                self.onWindowClose()

        DialogsInterface.showI18nConfirmDialog(dialogID, callback)

    ###
    # Added Methods
    ###
	



