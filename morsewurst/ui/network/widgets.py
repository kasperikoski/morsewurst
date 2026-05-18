# ============================================================
# morsewurst/ui/network/widgets.py
# ============================================================

from __future__ import annotations

import tkinter as tk

from morsewurst.ui.network_matrix_theme import MatrixTheme, make_label

class NetworkWidgetsMixin:
    def _make_scrollable_list(self, parent: tk.Misc, *, height: int) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, background=MatrixTheme.panel)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            outer,
            background=MatrixTheme.panel,
            highlightthickness=0,
            bd=0,
            height=height,
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar_canvas = tk.Canvas(
            outer,
            width=10,
            background=MatrixTheme.panel,
            highlightthickness=0,
            bd=0,
        )
        scrollbar_canvas.grid(row=0, column=1, sticky="ns", padx=(6, 0))

        thumb_id = scrollbar_canvas.create_rectangle(
            2,
            0,
            8,
            40,
            fill=MatrixTheme.border_dim,
            outline=MatrixTheme.accent,
        )

        view_state = {"first": 0.0, "last": 1.0}

        def _update_scrollbar(first: str | float, last: str | float) -> None:
            try:
                first_f = float(first)
                last_f = float(last)
            except Exception:
                first_f = 0.0
                last_f = 1.0

            view_state["first"] = first_f
            view_state["last"] = last_f

            try:
                if first_f <= 0.0 and last_f >= 0.999:
                    scrollbar_canvas.grid_remove()
                    return

                scrollbar_canvas.grid()

                height_px = max(1, scrollbar_canvas.winfo_height())
                min_thumb_height = 36

                y1 = int(first_f * height_px)
                y2 = int(last_f * height_px)

                if y2 - y1 < min_thumb_height:
                    y2 = y1 + min_thumb_height

                if y2 > height_px:
                    y2 = height_px
                    y1 = max(0, y2 - min_thumb_height)

                scrollbar_canvas.coords(thumb_id, 2, y1, 8, y2)
            except Exception:
                pass

        canvas.configure(yscrollcommand=_update_scrollbar)

        inner = tk.Frame(canvas, background=MatrixTheme.panel)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(_event: tk.Event) -> None:
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                _update_scrollbar(view_state["first"], view_state["last"])
            except Exception:
                pass

        def _on_canvas_configure(event: tk.Event) -> None:
            try:
                canvas.itemconfigure(window_id, width=event.width)
                _update_scrollbar(view_state["first"], view_state["last"])
            except Exception:
                pass

        def _scroll_to_pointer(event: tk.Event) -> None:
            try:
                height_px = max(1, scrollbar_canvas.winfo_height())
                visible_fraction = max(0.05, view_state["last"] - view_state["first"])
                target = (event.y / height_px) - (visible_fraction / 2.0)
                target = max(0.0, min(1.0, target))
                canvas.yview_moveto(target)
            except Exception:
                pass

        def _on_mousewheel(event: tk.Event) -> None:
            try:
                delta = int(-1 * (event.delta / 120))
                canvas.yview_scroll(delta, "units")
            except Exception:
                pass

        def _on_linux_scroll_up(_event: tk.Event) -> None:
            try:
                canvas.yview_scroll(-3, "units")
            except Exception:
                pass

        def _on_linux_scroll_down(_event: tk.Event) -> None:
            try:
                canvas.yview_scroll(3, "units")
            except Exception:
                pass

        def _bind_mousewheel(_event: tk.Event) -> None:
            try:
                canvas.bind_all("<MouseWheel>", _on_mousewheel)
                canvas.bind_all("<Button-4>", _on_linux_scroll_up)
                canvas.bind_all("<Button-5>", _on_linux_scroll_down)
            except Exception:
                pass

        def _unbind_mousewheel(_event: tk.Event) -> None:
            try:
                canvas.unbind_all("<MouseWheel>")
                canvas.unbind_all("<Button-4>")
                canvas.unbind_all("<Button-5>")
            except Exception:
                pass

        def _bind_recursive_mousewheel(widget: tk.Misc) -> None:
            try:
                widget.bind("<Enter>", _bind_mousewheel)
                widget.bind("<Leave>", _unbind_mousewheel)
            except Exception:
                pass

            try:
                for child in widget.winfo_children():
                    _bind_recursive_mousewheel(child)
            except Exception:
                pass

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        inner.bind("<Enter>", _bind_mousewheel)
        inner.bind("<Leave>", _unbind_mousewheel)

        scrollbar_canvas.bind("<Button-1>", _scroll_to_pointer)
        scrollbar_canvas.bind("<B1-Motion>", _scroll_to_pointer)

        inner.columnconfigure(0, weight=1)

        setattr(inner, "_scroll_bind_mousewheel", _bind_mousewheel)
        setattr(inner, "_scroll_unbind_mousewheel", _unbind_mousewheel)

        return outer, inner

    def _bind_scrollwheel_to_tree(self, root: tk.Misc) -> None:
        bind_mousewheel = getattr(root, "_scroll_bind_mousewheel", None)
        unbind_mousewheel = getattr(root, "_scroll_unbind_mousewheel", None)

        if bind_mousewheel is None or unbind_mousewheel is None:
            return

        stack: list[tk.Misc] = [root]

        while stack:
            widget = stack.pop()

            try:
                widget.bind("<Enter>", bind_mousewheel, add="+")
                widget.bind("<Leave>", unbind_mousewheel, add="+")
            except Exception:
                pass

            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass

    def _empty_row(self, parent: tk.Misc, text: str) -> tk.Frame:
        row = tk.Frame(parent, background=MatrixTheme.panel_alt, padx=12, pady=10)
        row.columnconfigure(0, weight=1)

        make_label(
            row,
            text,
            foreground=MatrixTheme.text_dim,
            background=MatrixTheme.panel_alt,
            wraplength=320,
        ).grid(row=0, column=0, sticky="w")

        return row