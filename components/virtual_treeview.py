# virtual_treeview.py (v2.0)

import tkinter as tk
from tkinter import ttk
import uuid


class VirtualTreeview(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        treeview_kwargs = {
            'columns': kwargs.pop('columns', []),
            'displaycolumns': kwargs.pop('displaycolumns', None),
            'show': kwargs.pop('show', 'headings'),
            'selectmode': kwargs.pop('selectmode', 'extended')
        }
        self.right_click_callback = kwargs.pop('right_click_callback', None)

        if treeview_kwargs['displaycolumns'] is None:
            treeview_kwargs['displaycolumns'] = treeview_kwargs['columns']

        super().__init__(master, **kwargs)

        self.columns = treeview_kwargs['columns']
        self.displaycolumns = treeview_kwargs['displaycolumns']
        self.show = treeview_kwargs['show']
        self.selectmode = treeview_kwargs['selectmode']

        self._data = {}
        self._ordered_iids = []

        self._selection = set()
        self._focus = None
        self._anchor = None

        self._tree = ttk.Treeview(self, **treeview_kwargs)
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self._on_scroll)
        self._hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(xscrollcommand=self._hsb.set)

        self._tree.grid(row=0, column=0, sticky='nsew')
        self._vsb.grid(row=0, column=1, sticky='ns')
        self._hsb.grid(row=1, column=0, sticky='ew')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._tree.bind("<<TreeviewSelect>>", self._on_ui_select)
        self._tree.bind("<Button-1>", self._on_button1_press)
        self._tree.bind("<Button-3>", self._on_button3_press)  # Right-click
        self._tree.bind("<B1-Motion>", lambda e: "break")
        self._tree.bind("<MouseWheel>", self._on_mousewheel)
        self._tree.bind("<Button-4>", self._on_mousewheel)  # For Linux (scroll up)
        self._tree.bind("<Button-5>", self._on_mousewheel)  # For Linux (scroll down)


        self._tree.bind("<Up>", self._on_key_press)
        self._tree.bind("<Down>", self._on_key_press)
        self._tree.bind("<Prior>", self._on_key_press)  # Page Up
        self._tree.bind("<Next>", self._on_key_press)  # Page Down
        self._tree.bind("<Home>", self._on_key_press)
        self._tree.bind("<End>", self._on_key_press)

        self.bind("<Configure>", self._on_configure)

        self._first_visible_index = 0
        self._visible_rows = 0
        self._row_height = 20

        self.after(10, self._calculate_row_height)

    def _calculate_row_height(self):
        try:
            iid = self._tree.insert("", "end", text="dummy")
            bbox = self._tree.bbox(iid)
            if bbox:
                self._row_height = bbox[3]
            self._tree.delete(iid)
        except (tk.TclError, IndexError):
            self._row_height = 20
        if self._row_height <= 0:
            self._row_height = 20

    def _on_configure(self, event=None):
        new_visible_rows = max(1, self.winfo_height() // self._row_height)
        if new_visible_rows != self._visible_rows:
            self._visible_rows = new_visible_rows
            self._redraw_view()

    def _on_scroll(self, action, value, units=None):
        total_rows = len(self._ordered_iids)
        if total_rows == 0: return

        if action == "moveto":
            self._first_visible_index = int(float(value) * total_rows)
        elif action == "scroll":
            self._first_visible_index += int(value)

        self._first_visible_index = max(0, min(self._first_visible_index, total_rows - self._visible_rows))
        self._redraw_view()

    def _on_mousewheel(self, event):
        if not self._ordered_iids: return

        if event.num == 5 or event.delta < 0:
            delta = 1
        else:
            delta = -1

        self._first_visible_index += delta
        total_rows = len(self._ordered_iids)
        self._first_visible_index = max(0, min(self._first_visible_index, total_rows - self._visible_rows))
        self._redraw_view()
        return "break"

    def _on_button1_press(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid: return

        state = event.state
        is_shift = (state & 0x0001) != 0
        is_ctrl = (state & 0x0004) != 0
        is_cmd = (state & 0x20000) != 0

        if is_shift:
            self._handle_shift_select(iid, state)
        elif is_ctrl or (self.tk.call('tk', 'windowingsystem') == 'aqua' and is_cmd):
            self._handle_ctrl_select(iid)
        else:
            self._handle_single_select(iid)
        self.event_generate("<<TreeviewSelect>>")
        return "break"

    def _on_button3_press(self, event):
        if self.right_click_callback:
            self.right_click_callback(event)
        return "break"

    def _on_key_press(self, event):
        if not self._ordered_iids: return

        current_focus = self.focus()
        if not current_focus:
            current_focus = self._ordered_iids[0]

        try:
            idx = self._ordered_iids.index(current_focus)
            new_idx = idx

            if event.keysym == 'Up':
                new_idx = max(0, idx - 1)
            elif event.keysym == 'Down':
                new_idx = min(len(self._ordered_iids) - 1, idx + 1)
            elif event.keysym == 'Prior':  # Page Up
                new_idx = max(0, idx - self._visible_rows)
            elif event.keysym == 'Next':  # Page Down
                new_idx = min(len(self._ordered_iids) - 1, idx + self._visible_rows)
            elif event.keysym == 'Home':
                new_idx = 0
            elif event.keysym == 'End':
                new_idx = len(self._ordered_iids) - 1

            if new_idx != idx:
                new_focus_iid = self._ordered_iids[new_idx]
                self._handle_single_select(new_focus_iid)
                self.see(new_focus_iid)
                self.event_generate("<<TreeviewSelect>>")
                return "break"
        except ValueError:
            # If focus is somehow invalid, select the first item
            self._handle_single_select(self._ordered_iids[0])
            self.event_generate("<<TreeviewSelect>>")
            return "break"
    def _handle_single_select(self, iid):
        self._selection = {iid}
        self._focus = iid
        self._anchor = iid
        self._redraw_view()

    def _handle_ctrl_select(self, iid):
        if iid in self._selection:
            self._selection.remove(iid)
        else:
            self._selection.add(iid)
        self._focus = iid
        self._anchor = iid
        self._redraw_view()

    def _handle_shift_select(self, iid, state):
        if not self._anchor:
            # If there's no anchor, treat it as a single select and set the anchor
            self._handle_single_select(iid)
            return

        try:
            anchor_idx = self._ordered_iids.index(self._anchor)
            current_idx = self._ordered_iids.index(iid)

            start = min(anchor_idx, current_idx)
            end = max(anchor_idx, current_idx)

            new_selection = set(self._ordered_iids[start:end + 1])

            is_ctrl = (state & 0x0004) != 0
            is_cmd = (state & 0x20000) != 0

            if is_ctrl or (self.tk.call('tk', 'windowingsystem') == 'aqua' and is_cmd):
                self._selection.update(new_selection)
            else:
                self._selection = new_selection

            self._focus = iid
            self._redraw_view()
        except ValueError:
            self._handle_single_select(iid)

    def _on_ui_select(self, event=None):
        pass

    def _redraw_view(self, keep_selection=True):
        self._tree.delete(*self._tree.get_children())

        total_rows = len(self._ordered_iids)
        if total_rows == 0:
            self._vsb.set(0, 1)
            return

        start = self._first_visible_index
        end = min(start + self._visible_rows + 2, total_rows)

        visible_iids = []
        for i in range(start, end):
            iid = self._ordered_iids[i]
            item = self._data[iid]
            self._tree.insert("", "end", iid=iid, values=item.get('values', ()), tags=item.get('tags', ()))
            visible_iids.append(iid)

        if keep_selection:
            selection_to_show = self._selection.intersection(visible_iids)
            if selection_to_show:
                self._tree.selection_set(list(selection_to_show))
            if self._focus in visible_iids:
                self._tree.focus_set()
                self._tree.focus(self._focus)

        first = start / total_rows if total_rows > 0 else 0
        last = end / total_rows if total_rows > 0 else 1
        self._vsb.set(first, last)

    def _sync_data_order(self, ordered_iids):
        self._ordered_iids = ordered_iids
        self._first_visible_index = 0
        self._redraw_view()

    def insert(self, parent, index, iid=None, **kwargs):
        if iid is None:
            iid = uuid.uuid4().hex

        self._data[iid] = {
            'values': kwargs.get('values', ()),
            'tags': kwargs.get('tags', ())
        }

        if iid not in self._ordered_iids:
            if index == 'end':
                self._ordered_iids.append(iid)
            else:
                self._ordered_iids.insert(index, iid)

        self._redraw_view()
        return iid

    def delete(self, *iids):
        if not iids:
            self._data.clear()
            self._ordered_iids.clear()
            self._selection.clear()
            self._focus = None
            self._anchor = None
        else:
            for iid in iids:
                if iid in self._data:
                    del self._data[iid]
                if iid in self._ordered_iids:
                    self._ordered_iids.remove(iid)
                self._selection.discard(iid)
                if self._focus == iid: self._focus = None
                if self._anchor == iid: self._anchor = None
        self._redraw_view()

    def get_children(self, item=''):
        return tuple(self._ordered_iids)

    def heading(self, column, **kwargs):
        if 'command' in kwargs:
            cmd = kwargs['command']

            def wrapper():
                self.master.after(10, cmd)

            kwargs['command'] = wrapper
        return self._tree.heading(column, **kwargs)

    def column(self, column, **kwargs):
        return self._tree.column(column, **kwargs)

    def tag_configure(self, tagname, **kwargs):
        self._tree.tag_configure(tagname, **kwargs)

    def selection(self):
        return tuple(self._selection)

    def selection_set(self, iids):
        if isinstance(iids, str):
            iids = (iids,)
        self._selection = set(iids)
        if iids:
            self._focus = iids[0]
            self._anchor = iids[0]
        else:
            self._focus = None
            self._anchor = None
        self._redraw_view()

    def selection_add(self, iids):
        if isinstance(iids, str):
            iids = (iids,)
        self._selection.update(iids)
        self._redraw_view()

    def focus(self, iid=None):
        if iid is None:
            return self._focus
        if iid in self._data:
            self._focus = iid
            self.see(iid)
            self._redraw_view()
        return self._focus

    def see(self, iid):
        if iid not in self._ordered_iids:
            return

        index = self._ordered_iids.index(iid)

        if not (self._first_visible_index <= index < self._first_visible_index + self._visible_rows):
            self._first_visible_index = max(0, index - self._visible_rows // 2)
            total_rows = len(self._ordered_iids)
            self._first_visible_index = max(0, min(self._first_visible_index, total_rows - self._visible_rows))
            self._redraw_view()

        if self._tree.exists(iid):
            self._tree.see(iid)

    def exists(self, iid):
        return iid in self._data

    def item(self, iid, option=None, **kwargs):
        if not kwargs and option is not None:
            if option == "values":
                return self._data.get(iid, {}).get('values')
            elif option == "tags":
                return self._data.get(iid, {}).get('tags')

        if iid in self._data:
            if 'values' in kwargs:
                self._data[iid]['values'] = kwargs['values']
            if 'tags' in kwargs:
                self._data[iid]['tags'] = kwargs['tags']
            self._redraw_view()
            return

        return self._tree.item(iid, option=option, **kwargs)

    def set(self, iid, column, value):
        if iid in self._data:
            try:
                col_index = self.columns.index(column)
                values = list(self._data[iid]['values'])
                values[col_index] = value
                self._data[iid]['values'] = tuple(values)
                self._redraw_view()
            except (ValueError, IndexError):
                pass

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<TreeviewSelect>>":
            super().bind(sequence, func, add)
        else:
            self._tree.bind(sequence, func, add)