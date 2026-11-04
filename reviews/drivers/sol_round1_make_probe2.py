import ast
from pathlib import Path
folder=Path(__file__).resolve().parent
source=(folder/'probe.py').read_text()
prefix=source[:source.index('w = tour_module.make_window')]
tree=ast.parse(source)
functions='\n\n'.join(ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.lineno>110)
start='''
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer
QMenu.exec = lambda menu,*a,**k: menus.append(menu_info(menu))
QMenu.exec_ = QMenu.exec
w = tour_module.make_window(tour,AnalysisMode.LABELLED)
active(w)
tour_module.load(tour,tour_module.LABELLED)
step('list_context_menus',list_menus)
step('integration_controls',integration_controls)
step('settings_dirty_pages',settings)
step('add_inline_validation',add_validation)
step('resize_reflow',resize_and_scroll)
step('unlabelled_drop_and_controls',unlabelled)
active(w)
w.toolbar.compound_filter.setText('valine')
tour.pump(.2)
w.toolbar.compound_list.setCurrentRow(2)

def observe():
    focus=app.focusWidget()
    value={'compound':w.selected_compound_name(),'focus_type':type(focus).__name__,'focus_name':focus.objectName() if focus else None,'filter':w.toolbar.compound_filter.text(),'selected':w.graph_view.get_selected_samples(),'active':w.isActiveWindow(),'modal':type(app.activeModalWidget()).__name__,'pages': [p.title for p in w.settings_window._pages] if w.settings_window else None}
    (OUT/'live_state.json').write_text(json.dumps(value,indent=2))
    command=OUT/'command.py'
    if command.exists():
        code=command.read_text()
        command.unlink()
        try:
            exec(code,globals())
        except Exception:
            print(traceback.format_exc(),flush=True)
timer=QTimer()
timer.timeout.connect(observe)
timer.start(500)
print('READY_FOR_NATIVE',flush=True)
app.exec()
'''
(folder/'probe2.py').write_text(prefix+functions+'\n'+start)
