import configparser
import glob
import ntpath
import os
from pathlib import Path
import re
import subprocess

import urwid

home = str(Path.home())
config_file_path = os.path.join(home, '.noots.ini')
conf = configparser.ConfigParser()
conf.read(config_file_path)
NOOTS_PATH = conf['NOOTS']['note_path']
EDITOR = conf['NOOTS']['editor']
NOTE_FILE_EXT = '.noot'
LOGO  = """
    _   __            __
   / | / /___  ____  / /______
  /  |/ / __ \/ __ \/ __/ ___/
 / /|  / /_/ / /_/ / /_(__  )
/_/ |_/\____/\____/\__/____/

        """


def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


class SearchManager(object):
    def __init__(self):
        self._fn_cache = []
        self.refresh_fn_cache()
        self.matched_title = ''
        self.sorted_filenames = []

    def search(self, search_str):
        """
        Given a string pattern, find the note title that
        matches the most and return the filename.
        :param search_str: String to pattern match.
        :return filename: String of the matching note filename
        """
        suggestions = []
        pattern = '.*?'.join(search_str)
        regex = re.compile(pattern)

        for item in self._fn_cache:
            match = regex.search(item)
            if match:
                suggestions.append((len(match.group()), match.start(), item))
        try:
            sorted_files = sorted(suggestions)
            self.sorted_filenames = [x for len_match, _, x in sorted_files]
            self.matched_title = str(self.sorted_filenames[0])
        except IndexError:
            self.matched_title = ''

    def populate_sorted_filenames_from_fn_cache(self):
        self.sorted_filenames = self._fn_cache[:]

    def refresh_fn_cache(self):
        """Update filename cache using glob pattern."""
        glob_pat = os.path.join(NOOTS_PATH, '*{0}'.format(NOTE_FILE_EXT))
        file_list = glob.glob(glob_pat)
        self._fn_cache = [path_leaf(f).replace('{0}'.format(NOTE_FILE_EXT), '') for f in file_list]

    def read_from_match(self):
        read_path = os.path.join(NOOTS_PATH, self.matched_title + NOTE_FILE_EXT)
        try:
            with open(read_path) as fin:
                data = fin.read()

            return data
        except TypeError:
            pass


class _Edit(urwid.Edit):
    def insert_text(self, _):
        pass


class AppController(object):
    """Main Application Controller. Uses one method, _handle_input, for all input handling."""

    def __init__(self):
        self.suggestion_content = []
        self.main_lw = None
        self.main_suggestion_listbox = None
        self.suggestions_listbox_container = None
        self.help_text = ''
        self.header = None
        self.header_div = None
        self.header_pile = None
        self.search_level_text = ''
        self.search_box = None
        self.body_edit_text = None
        self.body = None
        self.main_frame = None
        self.main_box = None
        self.main_cols = None

        self._init_header()
        self._init_search_bar()
        self._init_suggestion_list_box()
        self._init_body()
        self._init_main_container()

        self.search_manager = SearchManager()
        self.search_chars = []

        # Fill note suggestion listbox with all notes on startup
        self.search_manager.populate_sorted_filenames_from_fn_cache()
        self._update_suggestion_list()

        self.loop = urwid.MainLoop(
            self.main_cols,
            unhandled_input=self._handle_input,
            input_filter=self._input_filter,
        )

    def _init_main_container(self):
        footer_text = ('foot', [
            "Noots  ",
            ('key', "|  (?) "), "help menu ",
        ])
        self.footer = urwid.AttrWrap(urwid.Text(footer_text), "foot")
        self.main_frame = urwid.Frame(
            body=self.body,
            header=self.header_pile,
            footer=self.footer)

        self.main_box = urwid.LineBox(self.main_frame)
        self.main_cols = urwid.Columns([('weight', 2, self.suggestions_listbox_container), ('weight', 5, self.main_box),])
        self.main_cols.set_focus(0)

    def _init_body(self):
        self.body_edit_text = _Edit('')
        self.body = urwid.Filler(self.body_edit_text, 'top')

    def _init_search_bar(self):
        self.search_level_text = urwid.Text('Search: ')
        self.search_box = urwid.LineBox(self.search_level_text)

    def _init_header(self):
        self.help_text = (" {logo}\n"
                          " Ctrl-P       | Focus search/title bar.\n"
                          " Ctrl-E       | Edit note.\n"
                          " Ctrl-L       | Redraw screen.\n"
                          " Right Arrow  | Focus note text.\n"
                          " Alt (hold)   | copy text.\n".format(logo=LOGO))
        self.header = urwid.Text(self.help_text)
        self.header_div = urwid.Divider('.')
        self.header_pile = urwid.Pile([self.header, self.header_div])

    def _init_suggestion_list_box(self):
        self.suggestion_content = [self.search_box, urwid.Divider()]

        self.main_lw = urwid.SimpleFocusListWalker(self.suggestion_content)
        self.main_suggestion_listbox = urwid.ListBox(self.main_lw)

        self.suggestions_listbox_container = urwid.Padding(self.main_suggestion_listbox, left=2, right=2)

    def _show_help(self):
        self.header.set_text(self.help_text)

    def _update_suggestion_list(self, clean=False):
        suggestion_content = [self.search_box, urwid.Divider()]

        if not clean:
            for label in self.search_manager.sorted_filenames:
                b = urwid.Button(label)
                urwid.connect_signal(b, 'click', self._on_list_item_clicked, label)
                suggestion_content.append(urwid.AttrMap(b, None, focus_map='reversed'))

        self.main_lw[:] = urwid.SimpleFocusListWalker(suggestion_content)

    def _on_list_item_clicked(self, button, label):
        self._update(search_string=label, update_list=False)

    def _save_note(self):
        if self.search_manager.matched_title:
            title = self.search_manager.matched_title
        else:
            title = ''.join(self.search_chars)

        title = title.replace(' ', '_')
        title_fn = title + NOTE_FILE_EXT

        filepath = os.path.join(NOOTS_PATH, title_fn)

        with open(filepath, 'w') as fout:
            fout.write(self.body_edit_text.get_edit_text())

        self.search_manager.refresh_fn_cache()
        self._update(title)

    def _set_body(self, text):
        self.body_edit_text.set_edit_text(text)

    def _set_header(self, text):
        self.header.set_text(text)

    def _set_search_text(self, text):
        self.search_level_text.set_text(text)

    def _focus_search_column(self):
        self.main_cols.set_focus(0)

    def _move_suggestion_focus(self, direction):
        def _move():
            try:
                if direction == 'down':
                    self.main_lw.set_focus(
                        self.main_lw.next_position(
                            self.main_lw.get_focus()[1]
                        )
                    )
                elif direction == 'up':
                    self.main_lw.set_focus(
                        self.main_lw.prev_position(
                            self.main_lw.get_focus()[1]
                        )
                    )
            except IndexError:
                pass

        return _move

    def _delete_search_char(self):
        try:
            self.search_chars.pop()
        except IndexError:
            pass

    def _handle_input(self, key):
        """Any keypress that is not handled by the Listwalker (Up, Down)
           or the Edit widget will bubble up to this method. It would probably be
           better to have the individual widgets implement their own keypress, but
           with such a simple UI, this should be fine.
        """
        directional_keys = ('up', 'down', 'right', 'left')
        blacklist = ('backspace', 'enter', 'meta')
        key_action_map = {
            '?': (self._show_help, True),
            'ctrl d': (self._save_note, True),
            'ctrl e': (self._open_file_in_editor, True),
            'ctrl p': (self._focus_search_column, True),
            'ctrl l': (self._update, True),
            'esc': (self._clear, True),
            'J': (self._move_suggestion_focus('down'), True),
            'K': (self._move_suggestion_focus('up'), True),
            'backspace': (self._delete_search_char, False),
        }
        try:
            key_action_map[key][0]()
            should_return = key_action_map[key][1]

            if should_return:
                return

        except KeyError:
            pass

        if key in directional_keys:
            return

        if type(key) == str and key not in blacklist:
            self.search_chars.append(key)

        try:
            self._update()
        except:
            pass

    def _input_filter(self, keys, raw):
        try:
            if keys[0] == ' ':
                self._handle_input(keys[0])
                return
        except IndexError:
            self._handle_input('esc')

        return keys

    def _update(self, search_string='', update_list=True):
        if not self.search_chars:
            self._set_body('')

        search_string = search_string or ''.join(self.search_chars).strip()
        display_txt = "Search:  {0}".format(search_string)
        self._set_search_text(display_txt)

        self.search_manager.search(search_string.replace(' ', '_'))

        if update_list:
            self._update_suggestion_list()

        if self.search_manager.matched_title:
            try:
                self._set_body(self.search_manager.read_from_match())
            except AttributeError:
                pass

            self._set_header(self.search_manager.matched_title)
        else:
            if search_string:
                self._set_header('(New): {0}{1}'.format(
                    search_string.replace(' ', '_'),
                    NOTE_FILE_EXT)
                )

            self._set_body('')

    def _exec_subproc(self, cmd):
        """Suspend screen and call a subprocess.
           :param cmd: Command to run.
           :type cmd: str
        """
        self.loop.screen.stop()
        subprocess.call([cmd], shell=True)
        self.loop.screen.start()
        self.loop.start()

    def _open_file_in_editor(self):
        """Open either the matched note or a new note in the user's editor of choice."""
        filename = self.search_manager.matched_title or ''.join(self.search_chars).strip()
        filename = filename.replace(' ', '_')

        if not filename:
            return

        fq_filename = filename + NOTE_FILE_EXT
        filepath = os.path.join(NOOTS_PATH, fq_filename)
        self._exec_subproc('{0} {1}'.format(EDITOR, filepath))
        self.search_manager.refresh_fn_cache()
        self.search_manager.matched_title = filename
        self._set_body(self.search_manager.read_from_match())
        self._set_header(filename)

    def _clear(self):
        """Reset application state."""
        self.search_chars[:] = []
        self._update()
        self._set_body('')
        self._set_header(self.help_text)
        self.main_cols.set_focus(0)

    def main(self):
        self.loop.run()


if __name__ == '__main__':
    controller = AppController()
    controller.main()
