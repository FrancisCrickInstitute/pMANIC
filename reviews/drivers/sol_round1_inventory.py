import ast,json,subprocess
from pathlib import Path
ROOT=Path('/Users/couttsj/Documents/_code/pythonMANIC')
OUT=Path(__file__).resolve().parent
files=['main_window.py','graphs.py','compound_list_widget.py','sample_list_widget.py','settings_window.py','integration_window_widget.py','add_compound_dialog.py','detailed_plot_dialog.py','matplotlib_plot_widget.py','documentation_viewer.py','update_old_data_dialog.py','compound_recovery_dialog.py','sample_recovery_dialog.py']
result={}
for filename in files:
    path='src/manic/ui/'+filename
    old=subprocess.check_output(['git','show','f55caa6:'+path],cwd=ROOT,text=True)
    new=(ROOT/path).read_text()
    data=[]
    for source in (old,new):
        calls=[]
        attrs=[]
        tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                fn=node.func
                name=fn.attr if isinstance(fn,ast.Attribute) else fn.id if isinstance(fn,ast.Name) else ''
                if name in ('QAction','addAction','addMenu','addRow','form_row','QPushButton','QCheckBox','QRadioButton'):
                    strings=[x.value for x in node.args if isinstance(x,ast.Constant) and isinstance(x.value,str)]
                    if strings:calls.append([name,strings,node.lineno])
            if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
                fn=node.value.func
                name=fn.attr if isinstance(fn,ast.Attribute) else fn.id if isinstance(fn,ast.Name) else ''
                if name.startswith('Q') or any(x in name for x in ('spin','edit','combo')):
                    for target in node.targets:
                        if isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name) and target.value.id=='self':attrs.append(target.attr)
        data.append({'calls':calls,'controls':sorted(set(attrs))})
    old_labels={s for call,strings,line in data[0]['calls'] for s in strings}
    new_labels={s for call,strings,line in data[1]['calls'] for s in strings}
    result[filename]={'removed_labels':sorted(old_labels-new_labels),'added_labels':sorted(new_labels-old_labels),'removed_control_attributes':sorted(set(data[0]['controls'])-set(data[1]['controls'])),'baseline':data[0],'head':data[1]}
(OUT/'control_inventory.json').write_text(json.dumps(result,indent=2))
for f,v in result.items():print(f, json.dumps({k:v[k] for k in ('removed_labels','added_labels','removed_control_attributes')}))
