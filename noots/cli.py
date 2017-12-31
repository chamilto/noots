import configparser
import glob
import os
import ntpath
import re
from pathlib import Path

import urwid


home = str(Path.home())
config_file_path = os.path.join(home, '.noots.ini')
conf = configparser.ConfigParser()
conf.read(config_file_path)
NOOTS_PATH = conf['NOOTS']['note_path']


def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


class SearchManager(object):
    def __init__(self):
        self._fn_cache = []
        self.refresh_fn_cache()
        self.matched_title = ''

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
            sorted_filenames = sorted(suggestions)
            self.matched_title = str([x for len_match, _, x in sorted_filenames if len_match > 1][0])
        except IndexError:
            self.matched_title = ''

    def refresh_fn_cache(self):
        """Update filename cache using glob pattern."""
        glob_pat = os.path.join(NOOTS_PATH, '*.noot')
        file_list = glob.glob(glob_pat)
        self._fn_cache = [path_leaf(f) for f in file_list]

    def read_from_match(self):
        read_path = os.path.join(NOOTS_PATH, self.matched_title)
        try:
            with open(read_path) as fin:
                data = fin.read()

            return data
        except TypeError:
            pass


class CLI(object):
    """Main CLI Object. Uses one method, input_callback, for all input handling.
       Input handling can move to individual widgets if this becomes burdensome.
    """
    def __init__(self):
        self.search_level_text = urwid.Text('Search:    ')
        self.body_edit_text = urwid.Edit('', multiline=True)
        self.body = urwid.Filler(self.body_edit_text, 'top')
        self.header_text = ("Wecome to Noots! Ctrl-D anytime to save current note. \n"
                            "Ctrl-x to focus search/title bar. Press Ctrl-e to focus note editor\n"
                            "Hold alt to copy text.\n"
                            "Press Ctrl-? to view this section again.")
        self.header = urwid.Text(self.header_text)
        self.header_div = urwid.Divider('.')
        self.header_pile = urwid.Pile([self.header, self.header_div])
        self.search_box = urwid.LineBox(self.search_level_text)
        self.main_frame = urwid.Frame(
            body=self.body,
            header=self.header_pile,
            footer=self.search_box,
            focus_part='footer'
        )
        self.main_box = urwid.LineBox(self.main_frame)
        self.search_manager = SearchManager()
        self.search_chars = []

    def show_help(self):
        """Actions to perform before any handled input"""
        self.header.set_text(self.header_text)

    def save_note(self):
        title = ''.join(self.search_chars) + '.noot'
        title = title.replace(' ', '_')
        filepath = os.path.join(NOOTS_PATH, title)
        with open(filepath, 'w') as fout:
            fout.write(self.body_edit_text.get_edit_text())

        self.search_manager.refresh_fn_cache()
        self.set_header('Saved!')

    def reset_header(self):
        if self.search_manager.matched_title:
            self.set_header(self.search_manager.matched_title)

    def set_body(self, text):
        self.body_edit_text.set_edit_text(text)

    def set_header(self, text):
        self.header.set_text(text)

    def input_callback(self, key):
        if key == '?' and self.main_frame.focus_position == 'footer':
            self.show_help()
            return

        if key == 'ctrl d':
            self.save_note()
            return

        self.reset_header()


        if key in  ('up', 'ctrl e'):
            self.main_frame.set_focus('body')
            return

        if key == 'ctrl x':
            self.main_frame.set_focus('footer')
            return

        if key == 'backspace':
            try:
                self.search_chars.pop()
            except IndexError:
                pass
        else:
            self.search_chars.append(key)

        self.update()

    def update(self):
        if not self.search_chars:
            self.body_edit_text.set_edit_text('')

        search_string = ''.join(self.search_chars).strip()
        display_txt = "Search:  {0}".format(search_string)
        self.search_level_text.set_text(display_txt)

        self.search_and_set_body_and_header(search_string)


    def search_and_set_body_and_header(self, search_string):
        self.search_manager.search(search_string)

        if self.search_manager.matched_title:
            try:
                self.set_body(self.search_manager.read_from_match())
            except AttributeError:
                pass
            self.set_header(self.search_manager.matched_title)
        else:
            if search_string:
                self.set_header('(New): {0}.noot'.format(search_string.replace(' ', '_')))
            else:
                self.set_header('Welcome to Noots!')

            self.set_body('')



    def main(self):
        loop = urwid.MainLoop(self.main_box, unhandled_input=self.input_callback)
        loop.run()

