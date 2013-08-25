# coding: utf-8
#
# Copyright (C) 2012  Niklas Rosenstein
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
""" BatchRenderPostScript - Utility for Cinema 4D's BatchRender
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A tool for running Python scripts after the Batch Render has finished
    rendering.

    How it works
    ------------

    When a script was compiled with the dialog and the `Running` checkmarked
    activated, a thread is started which periodically checks if the Batch
    Render is done. When this is the case, the script is executed.

    .. author:: Niklas Rosenstein <rosensteinniklas@gmail.com>
    .. version:: 0.1.0
    .. date:: October 26. 2012
    .. license:: GNU GPL
    .. homepage:: https://github.com/NiklasRosenstein/c4d-brps
    """

__author__ = {'name': 'Niklas Rosenstein',
              'email': 'rosensteinniklas@gmail.com'}
__license__ = 'GNU GPL'
__version__ = (0, 1, 0)
__changed__ = (10, 26, 2012)

import os
import re
import sys
import c4d
import time
import hashlib
import threading
import traceback
import webbrowser
import collections

from c4d.documents import GetBatchRender
from c4d.plugins import GeLoadString

md5 = lambda x: hashlib.md5(x).hexdigest()
dirname = os.path.dirname(__file__)

# Symbols from the `c4d_symbols.h` file.
symbols = type('', (), {
    'DLG_BATCHRENDERPOSTSCRIPT': 10001,
    'GRP_ALL': 10002,
    'GRP_OPTIONS': 10003,
    'CHK_RUNNING': 10004,
    'STATIC_INFO': 10005,
    'BTN_OPENBR': 10006,
    'GRP_SCRIPT': 10007,
    'EDT_SCRIPT': 10008,
    'GRP_SCRIPT_ACTIONS': 10009,
    'BTN_SCRIPT_COMPILE': 10010,
    'STATIC_SCRIPT_INFO': 10011,
    'UA_SCRIPT_COMPILEOK': 10012,
    'STR_BR_NOT_RUNNING': 10013,
    'STR_ERROR': 10014,
    'STR_NO_MAIN_METHOD': 10015,
    'STR_MAIN_NOT_CALLABLE': 10016,
    'STR_SCRIPT_NOT_COMPILED': 10017,
    'STR_MENU_FILE': 10018,
    'STR_MENU_FILE_LOAD': 10019,
    'STR_MENU_FILE_SAVE': 10020,
    'STR_MENU_ABOUT': 10021,
    'STR_MENU_ABOUT_SHOW': 10022,
    'STR_MENU_ABOUT_CONTACT': 10023,
    'DLG_ABOUT': 10024,
})

# (internal) global options for the plugin.
options = {
    # The regular expression here must yield two groups both consisting of
    # digits only that define the line and the column of the cursor to be
    # positioned when a script is loaded.
    'jump-to-expr': re.compile('^\s*#\s*jump-to:\s*(\d+),\s*(\d+)'),

    # Several resources.
    'img:brps-icon': 'brps-command.png',
    'img:icon-ok': 'icon-ok.png',
    'img:icon-notok': 'icon-notok.png',
    'res:default-code': 'default.py',
}

# Process the options and convert all keys prefixed with `path:` to absolute
# paths pointing to the plugins `res` folder. The `path:` prefix is removed.
for k in options.keys():
    if k.startswith('res:'):
        new_k = k[len('res:'):]
        new_v = os.path.join(dirname, 'res', options[k])
    elif k.startswith('img:'):
        new_k = k[len('img:'):]
        new_v = os.path.join(dirname, 'res', 'img', options[k]) 
    else:
        continue

    options[new_k] = new_v
    del options[k]


class BrpsThread(threading.Thread):

    def __init__(self, method, sleeptime=1.0):
        super(BrpsThread, self).__init__()
        self.method = method
        self.sleeptime = sleeptime
        self.running = False

    def work_out(self):
        br = GetBatchRender()
        if not br.IsRendering():

            try:
                self.method()
            except Exception as e:
                print
                print "Batch Render Post Script: Exception occured."
                traceback.print_exc()
            self.abandon()

    def abandon(self):
        self.running = False

    def is_running(self):
        return self.running

  # threading.Thread

    def run(self):
        self.running = True

        while self.running:
            self.work_out()
            time.sleep(self.sleeptime)

class BrpsCommand(c4d.plugins.CommandData):

    PLUGIN_ID = 1029245
    PLUGIN_NAME = 'Batch Render Post Script'
    PLUGIN_ICON = options['brps-icon']
    PLUGIN_HELP = 'Run a script after the Batch Render has finished rendering.'
    PLUGIN_INFO = c4d.PLUGINFLAG_COMMAND_HOTKEY

    def __init__(self):
        super(BrpsCommand, self).__init__()
        self._dialog = None

    @property
    def dialog(self):
        if not self._dialog:
            self._dialog = BrpsDialog()
        return self._dialog

    @classmethod
    def register(cls):
        icon = None
        if cls.PLUGIN_ICON:
            icon = c4d.bitmaps.BaseBitmap()
            icon.InitWith(cls.PLUGIN_ICON)
        return c4d.plugins.RegisterCommandPlugin(cls.PLUGIN_ID, cls.PLUGIN_NAME,
                cls.PLUGIN_INFO, icon, cls.PLUGIN_HELP, cls())

  # c4d.plugins.CommandData

    def Execute(self, doc):
        self.dialog.Open(c4d.DLG_TYPE_ASYNC, pluginid=self.PLUGIN_ID)
        return True

    def RestoreLayout(self, secret):
        return self.dialog.Restore(self.PLUGIN_ID, secret)

class BrpsDialog(c4d.gui.GeDialog):

    BITMAP_ICON_OK = c4d.bitmaps.BaseBitmap()
    BITMAP_ICON_OK.InitWith(options['icon-ok'])
    BITMAP_ICON_NOTOK = c4d.bitmaps.BaseBitmap()
    BITMAP_ICON_NOTOK.InitWith(options['icon-notok'])

    CMD_LOADFILE = 1000
    CMD_SAVEFILE = 1001
    CMD_SHOWABOUT = 1002
    CMD_CONTACTDEV = 1003

    def __init__(self):
        super(BrpsDialog, self).__init__()
        self.post_method = None
        self.thread = None
        self.icon_ua = None
        self.script_hash = ''

    @property
    def running(self):
        return self.GetBool(symbols.CHK_RUNNING)

    @running.setter
    def running(self, v):
        self.SetBool(symbols.CHK_RUNNING, not not v)

    def enable_running(self, value, text, *args):
        value = not not value
        if isinstance(text, int):
            text = GeLoadString(text, *args)

        if not value:
            self.SetBool(symbols.CHK_RUNNING, False)

        self.Enable(symbols.CHK_RUNNING, value)
        self.SetString(symbols.STATIC_INFO, text)
        self.LayoutChanged(symbols.GRP_OPTIONS)

    def check_br(self):
        br = GetBatchRender()
        if not br.IsRendering():
            string = GeLoadString(symbols.STR_BR_NOT_RUNNING)
            reval = False
        else:
            string = ''
            reval = True

        self.enable_running(reval, string)
        if not reval:
            self.abandon_thread()

        return reval

    def check_script(self):
        code = self.GetString(symbols.EDT_SCRIPT)
        self.script_changed(update=True)
        message = ''
        scope = {}

        try:
            exec code in scope
        except Exception as e:
            # Obtain more information about the traceback.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            exc_name = exc_type.__name__

            # Set the cursor in the edit-field to the line where the error
            # occured.
            while exc_tb.tb_next:
                exc_tb = exc_tb.tb_next

            line = exc_tb.tb_lineno
            if isinstance(e, SyntaxError):
                line = e.lineno
            self.SetMultiLinePos(symbols.EDT_SCRIPT, line, 0)

            # Load the message and print the traceback to the console.
            message = GeLoadString(symbols.STR_ERROR, exc_name)
            traceback.print_exc()
        else:
            # Obtain the main-method from the execution-scope.
            self.post_method = scope.get('main')
            if not self.post_method:
                message = GeLoadString(symbols.STR_NO_MAIN_METHOD)
            elif not isinstance(self.post_method, collections.Callable):
                message = GeLoadString(symbols.STR_MAIN_NOT_CALLABLE)

        is_ok = not message
        if not is_ok:
            self.abandon_thread()

        self.change_icon(is_ok)
        self.set_script_info(message)
        return is_ok

    def script_changed(self, update):
        code = self.GetString(symbols.EDT_SCRIPT)
        hash = md5(code)
        if hash != self.script_hash:
            if update:
                self.script_hash = hash
            return True
        return False

    def change_icon(self, mode):
        if mode:
            icon = self.BITMAP_ICON_OK
        else:
            icon = self.BITMAP_ICON_NOTOK
        self.icon_ua.change_bitmap(icon)

    def set_script_info(self, text, *args):
        if isinstance(text, int):
            text = GeLoadString(text, *args)

        self.SetString(symbols.STATIC_SCRIPT_INFO, text)
        self.LayoutChanged(symbols.GRP_SCRIPT_ACTIONS)

    def load_file(self, filename):
        if os.path.isfile(filename):
            with open(filename) as fl:
                first_line = fl.readline()
                code = first_line + fl.read()
        else:
            code = ''
            first_line = ''

        self.SetString(symbols.EDT_SCRIPT, code)

        # Check if we should jump to a specific line which is indicated
        # by the first line in the loaded code.
        jump_to = options['jump-to-expr'].match(first_line)
        if jump_to:
            line, column = map(int, jump_to.groups())
            self.SetMultiLinePos(symbols.EDT_SCRIPT, line, column)

    def abandon_thread(self):
        if self.thread:
            self.thread.abandon()
        self.thread = None

    def try_run(self):
        do_abandon = not self.post_method
        do_abandon = do_abandon or (not self.running)

        if do_abandon:
            self.abandon_thread()
        elif self.running and not (self.thread and self.thread.is_running()):
            self.thread = BrpsThread(self.post_method)
            self.thread.start()

  # c4d.gui.GeDialogl

    def CreateLayout(self):
        # Create the MenuBar items.
        self.GroupBeginInMenuLine()
        self.MenuSubBegin(GeLoadString(symbols.STR_MENU_FILE))
        self.MenuAddString(self.CMD_LOADFILE, GeLoadString(symbols.STR_MENU_FILE_LOAD))
        self.MenuAddString(self.CMD_SAVEFILE, GeLoadString(symbols.STR_MENU_FILE_SAVE))
        self.MenuSubEnd()
        self.MenuFinished()

        self.MenuSubBegin(GeLoadString(symbols.STR_MENU_ABOUT))
        self.MenuAddString(self.CMD_SHOWABOUT, GeLoadString(symbols.STR_MENU_ABOUT_SHOW))
        self.MenuAddString(self.CMD_CONTACTDEV, GeLoadString(symbols.STR_MENU_ABOUT_CONTACT))
        self.MenuSubEnd()
        self.GroupEnd()

        return self.LoadDialogResource(symbols.DLG_BATCHRENDERPOSTSCRIPT)

    def InitValues(self):
        self.icon_ua = BitmapArea(None)
        self.AttachUserArea(self.icon_ua, symbols.UA_SCRIPT_COMPILEOK)

        self.load_file(options['default-code'])
        self.check_br()
        self.check_script()
        return True

    def Command(self, id, msg):
        if id == symbols.EDT_SCRIPT:
            if self.script_changed(update=False):
                self.post_method = None
                self.enable_running(False, symbols.STR_SCRIPT_NOT_COMPILED)
                self.abandon_thread()
                self.change_icon(False)
        elif id == symbols.BTN_SCRIPT_COMPILE:
            self.check_script()
            self.check_br()
            self.abandon_thread()
            self.try_run()
        elif id == symbols.CHK_RUNNING:
            self.try_run()
        elif id == symbols.BTN_OPENBR:
            br = GetBatchRender()
            if br:
                br.Open()
        elif id == self.CMD_LOADFILE:
            filename = c4d.storage.LoadDialog()
            if filename and os.path.isfile(filename):
                self.load_file(filename)
        elif id == self.CMD_SAVEFILE:
            filename = c4d.storage.SaveDialog()
            if filename:
                string = self.GetString(symbols.EDT_SCRIPT)
                with open(filename, 'wb') as fl:
                    fl.write(string)
        elif id == self.CMD_SHOWABOUT:
            BrpsAboutDialog().Open()
        elif id == self.CMD_CONTACTDEV:
            webbrowser.open('mailto:%s' % __author__['email'])

        return True

    def CoreMessage(self, id, msg):
        if id in [c4d.BFM_CORE_UPDATECOMMANDS, c4d.EVMSG_UPDATEHIGHLIGHT]:
            self.check_br()

        return super(BrpsDialog, self).CoreMessage(id, msg)

    def SetMultiLinePos(self, id, line, column):
        # GeDialog.SetMultiLinePos is available R13.016 and higher. We
        # create/overwrite this method so we do not have to check in the
        # code where we use this method.
        if c4d.GetC4DVersion() >= 13016:
            return super(BrpsDialog, self).SetMultiLinePos(id, line, column)
        else:
            return True

class BrpsAboutDialog(c4d.gui.GeDialog):

    def __init__(self):
        super(BrpsAboutDialog, self).__init__()

  # c4d.gui.GeDialog

    def Open(self):
        return super(BrpsAboutDialog, self).Open(c4d.DLG_TYPE_MODAL)

    def CreateLayout(self):
        return self.LoadDialogResource(symbols.DLG_ABOUT)

class BitmapArea(c4d.gui.GeUserArea):

    def __init__(self, bmp, bgcolor=None):
        super(BitmapArea, self).__init__()
        self.bmp = bmp
        self.bgcolor = bgcolor

    def change_bitmap(self, bmp):
        self.bmp = bmp
        self.Redraw()

  # c4d.gui.GeUserArea

    def DrawMsg(self, x1, y1, x2, y2, msg):
        # Determine the background-color. The `bgcolor` attribute may be a
        # callable not accepting arguments.
        if not self.bgcolor:
            # NOTE: I'm not sure if this will always yield the correct
            # interface color. However, I couldn't find a better one.
            bgcolor = c4d.GetViewColor(c4d.VIEWCOLOR_GRID_MINOR)
        elif isinstance(self.bgcolor, collections.Callable):
            bgcolor = self.bgcolor()
        else:
            bgcolor = self.bgcolor

        self.DrawSetPen(self.bgcolor)
        self.DrawRectangle(x1, y1, x2, y2)

        if self.bmp:
            w, h = self.bmp.GetSize()
            self.DrawBitmap(self.bmp, x1, y1, x2, y2, 0, 0, w, h,
                            c4d.BMP_ALLOWALPHA)


def main():
    BrpsCommand.register()

if __name__ == '__main__':
    main()


