import configparser
import glob
import ntpath
import os
from pathlib import Path
import re

import urwid

home = str(Path.home())
config_file_path = os.path.join(home, '.noots.ini')
conf = configparser.ConfigParser()
conf.read(config_file_path)
NOOTS_PATH = conf['NOOTS']['note_path']
LOGO  = """
    _   __            __
   / | / /___  ____  / /______
  /  |/ / __ \/ __ \/ __/ ___/
 / /|  / /_/ / /_/ / /_(__  )
/_/ |_/\____/\____/\__/____/
        """

NOTE_FILE_EXT = '.noot'


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


class AppController(object):
    """Main Application Controller. Uses one method, handle_input, for all input handling."""

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
        self.body_edit_text = urwid.Edit('', multiline=True)
        self.body = urwid.Filler(self.body_edit_text, 'top')

    def _init_search_bar(self):
        self.search_level_text = urwid.Text('Search: ')
        self.search_box = urwid.LineBox(self.search_level_text)

    def _init_header(self):
        self.help_text = ("{logo}\n"
                            "Ctrl-D anytime to save current note. \n"
                            "Ctrl-P to focus search/title bar.\n"
                            "Press Ctrl-E to focus note editor\n"
                            "Hold alt to copy text.\n".format(logo=LOGO))
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
        self.update(search_string=label, update_list=False)

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
        self.update(title)

    def _set_body(self, text):
        self.body_edit_text.set_edit_text(text)

    def _set_header(self, text):
        self.header.set_text(text)

    def _set_search_text(self, text):
        self.search_level_text.set_text(text)

    def handle_input(self, key):
        """Any keypress that is not handled by the Listwalker (Up, Down)
           or the Edit widget will bubble up to this method. It would probably be
           better to have the individual widgets implement their own keypress, but
           with such a simple UI, this should be fine.
        """
        if key == '?':
            self._show_help()
            return

        if key == 'ctrl d':
            self._save_note()
            return

        if key in  ('up', 'ctrl e'):
            self.main_frame.set_focus('body')
            self.main_cols.set_focus(1)
            return

        if key == 'ctrl p':
            self.main_cols.set_focus(0)
            return

        if key == 'esc':
            self.search_chars[:] = []
            self.update()
            self._set_body('')
            self._set_header('')
            self.main_cols.set_focus(0)
            return

        if key == 'backspace':
            try:
                self.search_chars.pop()
            except IndexError:
                pass
        elif key not in ('enter', 'meta', 'down', 'up', 'right', 'left') and type(key) == str:
            self.search_chars.append(key)

        try:
            self.update()
        except:
            pass

    def update(self, search_string='', update_list=True):
        if not self.search_chars:
            self._set_body('')

        search_string = search_string or ''.join(self.search_chars).strip()
        display_txt = "Search:  {0}".format(search_string)
        self._set_search_text(display_txt)

        self.search_manager.search(search_string)

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

    def main(self):
        self.loop = urwid.MainLoop(self.main_cols, unhandled_input=self.handle_input)
        self.loop.run()


if __name__ == '__main__':
    controller = AppController()
    controller.main()
