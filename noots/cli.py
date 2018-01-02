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
            self.sorted_filenames = sorted(suggestions)
            self.matched_title = str([x for len_match, _, x in self.sorted_filenames][0])
        except IndexError:
            self.matched_title = ''

    def refresh_fn_cache(self):
        """Update filename cache using glob pattern."""
        glob_pat = os.path.join(NOOTS_PATH, '*.noot')
        file_list = glob.glob(glob_pat)
        self._fn_cache = [path_leaf(f).replace('.noot', '') for f in file_list]

    def read_from_match(self):
        read_path = os.path.join(NOOTS_PATH, self.matched_title + '.noot')
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
        self.suggestion_content = []
        self.main_lw = None
        self.main_suggestion_listbox = None
        self.suggestions_listbox = None
        self.header_text = ''
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

        self.init_header()
        self.init_search_bar()
        self.init_suggestion_list_box()
        self.init_body()
        self.init_main_container()

        self.search_manager = SearchManager()
        self.search_chars = []

        # match all
        self.search_manager.search('.noots')
        self.update()
        self.set_body('')
        self.set_header('')

    def init_main_container(self):
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
        self.main_cols = urwid.Columns([('weight', 2, self.suggestions_listbox), ('weight', 5, self.main_box),])
        self.main_cols.set_focus(0)

    def init_body(self):
        self.body_edit_text = urwid.Edit('', multiline=True)
        self.body = urwid.Filler(self.body_edit_text, 'top')

    def init_search_bar(self):
        self.search_level_text = urwid.Text('Search: ')
        self.search_box = urwid.LineBox(self.search_level_text)

    def init_header(self):
        logo  = """
    _   __            __
   / | / /___  ____  / /______
  /  |/ / __ \/ __ \/ __/ ___/
 / /|  / /_/ / /_/ / /_(__  )
/_/ |_/\____/\____/\__/____/
        """
        self.header_text = ("{logo}\n"
                            "Ctrl-D anytime to save current note. \n"
                            "Ctrl-P to focus search/title bar.\n"
                            "Press Ctrl-E to focus note editor\n"
                            "Hold alt to copy text.\n".format(logo=logo))
        self.header = urwid.Text(self.header_text)
        self.header_div = urwid.Divider('.')
        self.header_pile = urwid.Pile([self.header, self.header_div])

    def init_suggestion_list_box(self):
        self.suggestion_content = [self.search_box, urwid.Divider()]

        self.main_lw = urwid.SimpleFocusListWalker(self.suggestion_content)
        self.main_suggestion_listbox = urwid.ListBox(self.main_lw)

        suggestion_items = urwid.Padding(self.main_suggestion_listbox, left=2, right=2)
        self.suggestions_listbox = urwid.Overlay(suggestion_items, urwid.SolidFill(u'\N{MEDIUM SHADE}'),
        align='center', width=('relative', 100),
        valign='middle', height=('relative', 100),
        min_width=20, min_height=9)


    def show_help(self):
        self.header.set_text(self.header_text)

    def update_suggestion_list(self, clean=False):
        suggestion_content = [self.search_box, urwid.Divider()]

        if not clean:
            for item in self.search_manager.sorted_filenames:
                label = item[2]
                b = urwid.Button(label)
                urwid.connect_signal(b, 'click', self.on_list_item_clicked, label)
                suggestion_content.append(urwid.AttrMap(b, None, focus_map='reversed'))

        self.main_lw[:] = urwid.SimpleFocusListWalker(suggestion_content)

    def on_list_item_clicked(self, button, label):
        self.update(search_string=label, update_list=False)

    def save_note(self):
        title = ''.join(self.search_chars) + '.noot'
        title = title.replace(' ', '_')
        filepath = os.path.join(NOOTS_PATH, title)
        with open(filepath, 'w') as fout:
            fout.write(self.body_edit_text.get_edit_text())

        self.search_manager.refresh_fn_cache()
        self.set_header('Saved!')
        self.update()

    def reset_header(self):
        if self.search_manager.matched_title:
            self.set_header(self.search_manager.matched_title)

    def set_body(self, text):
        self.body_edit_text.set_edit_text(text)

    def set_header(self, text):
        self.header.set_text(text)

    def input_callback(self, key):
        if key == '?':
            self.show_help()
            return

        if key == 'ctrl d':
            self.save_note()
            return

        self.reset_header()


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
            self.set_body('')
            self.set_header('')
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
            self.body_edit_text.set_edit_text('')

        search_string = search_string or ''.join(self.search_chars).strip()
        display_txt = "Search:  {0}".format(search_string)
        self.search_level_text.set_text(display_txt)

        self.search_and_set_body_and_header(search_string, update_list)


    def search_and_set_body_and_header(self, search_string, update_list):
        self.search_manager.search(search_string)

        if update_list:
            self.update_suggestion_list()

        if self.search_manager.matched_title:
            try:
                self.set_body(self.search_manager.read_from_match())
            except AttributeError:
                pass
            self.set_header(self.search_manager.matched_title + '.noot')
        else:
            if search_string:
                self.set_header('(New): {0}.noot'.format(search_string.replace(' ', '_')))
            else:
                self.set_header('Welcome to Noots!')

            self.set_body('')


    def main(self):
        self.loop = urwid.MainLoop(self.main_cols, unhandled_input=self.input_callback)
        self.loop.run()
