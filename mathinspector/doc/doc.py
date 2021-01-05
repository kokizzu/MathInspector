import tkinter as tk
from tkinter import ttk
import inspect, __main__, re, os
from .tags import DOC_TAGS
from widget import Notebook, Treeview, Menu, Text
from style import Color, getimage
from util import argspec, FunctionDoc, open_editor, classname, EXCLUDED_MODULES, BUTTON_RIGHT, BUTTON_RELEASE_RIGHT, INSTALLED_PKGS, BUILTIN_PKGS
from .show_functiondoc import show_functiondoc
from .show_textfile import show_textfile
from numpy import ufunc

class Doc(tk.Frame):
	def __init__(self, parent, obj=None, has_sidebar=None, run_code=None, **kwargs):
		tk.Frame.__init__(self, parent, background=Color.BLACK)
		self.parent = parent
		self.paned_window = ttk.PanedWindow(self, orient="horizontal")

		frame = tk.Frame(self, background=Color.BACKGROUND)
		self.nav = Text(frame, padx=16, height=2, readonly=True, font="Nunito-ExtraLight 16", cursor="arrow", insertbackground=Color.BACKGROUND)
		self.text = Text(frame, readonly=True, has_scrollbar=True, font="Nunito-ExtraLight 16", cursor="arrow", insertbackground=Color.BACKGROUND)

		self.notebook = Notebook(self)
		self.tree = Treeview(self, drag=False)

		self.has_sidebar = (has_sidebar or inspect.ismodule(obj) or inspect.isclass(obj))
		self.run_code = run_code
		if self.has_sidebar:
			self.notebook.add("tree", self.tree)
			self.paned_window.add(self.notebook.frame)
			self.nav.pack(side="top", fill="x")

		self.text.pack(side="bottom", fill="both", expand=True)
		
		self.paned_window.add(frame)
		self.paned_window.pack(side="left", fill="both", expand=True)

		self.menu = Menu(self)
		self.functions = {}
		self.builtins = {}
		self.classes = {}
		self.submodules = {}

		self.parent.bind("<Escape>", lambda event: parent.destroy())
		self.text.bind("<Escape>", lambda event: parent.destroy())

		self.tree.tag_bind("submodule", "<ButtonRelease-1>", self._on_button_release_1)		
		self.tree.tag_bind("class", "<ButtonRelease-1>", self._on_button_release_1)		
		self.tree.bind("<<TreeviewSelect>>", self._on_select)

		for i in ("link_url", "doc_link", "code_sample", "submodule", "root"):
			self.text.tag_bind(i, "<Motion>", lambda event, key=i: self.text._motion(event, key))
			self.text.tag_bind(i, "<Leave>", lambda event, key=i: self.text._leave(event, key))
			self.text.tag_bind(i, "<Button-1>", lambda event, key=i: self._click(event, key))    
		
		self.nav.tag_bind("root", "<Button-1>", lambda event: self.show(self.rootmodule))
		self.nav.tag_bind("root", "<Motion>", lambda event, key=i: self.nav._motion(event, "root"))
		self.nav.tag_bind("root", "<Leave>", lambda event, key=i: self.nav._leave(event, "root"))    
		
		self.nav.tag_configure("root", **DOC_TAGS["root"])		
		self.nav.tag_configure("root_hover", **DOC_TAGS["root_hover"])		
		self.nav.tag_configure("module_nav", **DOC_TAGS["module_nav"])		
		for i in DOC_TAGS:
			self.text.tag_configure(i, **DOC_TAGS[i])

		if obj:
			self.show(obj)
		
	def show(self, obj, clear_nav=True):
		self.obj = obj

		# REFACTOR - what if there is no nav? clean these systems up
		if clear_nav:
			name = self.getname(obj)
			self.nav.delete("1.0", "end")
			self.nav.insert("end", name, ("root", "basepath"))
			self.rootmodule = self.obj
		else:
			name = self.getname(obj).split(".")[-1]
			self.nav.delete(self.nav.tag_ranges("basepath")[1], "end")
			self.nav.tag_remove("basepath", "1.0", "end")
			self.nav.insert("end", " > ", "blue")
			self.nav.insert("end", name, ("module_nav", "subpath", "basepath"))

		self.clear()

		if isinstance(obj, str) and os.path.isfile(obj):
			content = open(obj).read()
			show_textfile(self.text, content)
			return

		for i in dir(self.obj):
			attr = getattr(self.obj, i)
			if i[0] == "_":
				pass
			elif inspect.isclass(attr):
				self.classes[i] = attr
			elif inspect.ismodule(attr) and i not in INSTALLED_PKGS + BUILTIN_PKGS + EXCLUDED_MODULES + ["os", "sys"]:
				self.submodules[i] = attr
			elif inspect.isfunction(attr):
				self.functions[i] = attr
			elif callable(attr):
				self.builtins[i] = attr
			else:
				pass

		if self.builtins:
			if inspect.isclass(self.obj):
				parent = self.tree.insert("", "end", text="methods", open=True)
			else:
				parent = self.tree.insert("", "end", text="builtins", open=True)
			for j in self.builtins:
				self.tree.insert(parent, "end", j, text=j)

		if self.functions:
			functions = self.tree.insert("", "end", text="functions", open=True)		
			for j in self.functions:
				self.tree.insert(functions, "end", j, text=j, open=True)

		if self.classes:			
			classes = self.tree.insert("", "end", text="classes", open=True)		
			for k in self.classes:
				temp = self.tree.insert(classes, "end", k, text=k, tags="class")

		if self.submodules:			
			for i in self.submodules:
				self.tree.insert("", "end", i, image=getimage(".py"), text="      " + i, tags="submodule")
		
		if self.has_sidebar:
			if not self.builtins and not self.functions and not self.classes and not self.submodules:
				self.paned_window.sashpos(0,0)
			elif self.paned_window.sashpos(0) < 20:
				self.paned_window.sashpos(0,220)

		if inspect.ismodule(obj):
			show_textfile(self.text, inspect.getdoc(obj))
			self.toggle_scrollbar()
			return

		try:
			doc = FunctionDoc(obj)
		except Exception:
			show_textfile(self.text, inspect.getdoc(obj))
			self.toggle_scrollbar()
			return
		show_functiondoc(self.text, doc, classname(obj))
		self.toggle_scrollbar()

	# REFACTOR - need a better system for scrollbars in general
	def toggle_scrollbar(self):
		if self.text.yview()[1] == 1.0:
			self.text.scrollbar.pack_forget()
		elif not self.text.scrollbar.winfo_ismapped():
			if self.has_sidebar:
				self.text.scrollbar.pack(before=self.nav, side="right", fill="y")
			else:
				self.text.scrollbar.pack(before=self.text, side="right", fill="y")

	def getname(self, obj):
		return "mathinspector" if obj == __main__ else obj.__name__ if hasattr(obj, "__name__") else obj.__class__.__name__
	
	def clear(self):
		self.text.delete("1.0", "end")

		self.builtins.clear()
		self.functions.clear()
		self.classes.clear()
		self.submodules.clear()

		for i in self.tree.get_children():
			self.tree.delete(i)

	def _on_select(self, event):
		key = self.tree.selection()[0]
		if not hasattr(self.obj, key): return

		obj = getattr(self.obj, key)
		self.text.delete("1.0", "end")
		self.nav.delete(self.nav.tag_ranges("basepath")[1], "end")
		self.nav.insert("end", " > ", "blue")
		self.nav.insert("end", key, ("module_nav", "subpath"))
		try:
			doc = FunctionDoc(obj)
		except Exception:
			show_textfile(self.text, inspect.getdoc(obj))
			return
		show_functiondoc(self.text, doc, classname(obj))

	def _on_button_release_1(self, event):
		key = self.tree.selection()[0]
		self.show(getattr(self.obj, key), clear_nav=False)
	
	def _on_button_release_2(self, event, name):
		name = getattr(self, name).identify_row(event.y)
		obj = getattr(self.obj, name)
		try:
			file = inspect.getsourcefile(obj)
		except:
			file = None
		
		if file:
			self.menu.show(event, [{
				"label": "View Source Code",
				"command": lambda: open_editor(file)
			}])

	def _click(self, event, tag):
		if tag == "link_url":
			webbrowser.open(self.text.get(*self.hover_range), new=2)
		elif tag == "doc_link":
			doc_link = self.text.get(*self.text.hover_range)
			obj = getattr(__import__(self.obj.__class__.__module__), doc_link)
			self.show(obj)
		elif tag == "code_sample" and self.run_code:
			for command in re.findall(r">>> {0,}(.*)", self.text.get(*self.text.hover_range)):
				self.run_code(command)