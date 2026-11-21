"""Read a real STEP assembly with XDE names and locations; never edits the EDA file.
Usage: python inspect_step.py input.step output.json
"""
from pathlib import Path
import json,sys,hashlib
import cadquery as cq
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence,TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.TopLoc import TopLoc_Location


def name_of(label):
    a=TDataStd_Name()
    return a.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(),a) else ''


def read_named_shapes(path):
    reader=STEPCAFControl_Reader();doc=TDocStd_Document(TCollection_ExtendedString('PCBA'))
    status=reader.ReadFile(str(path))
    if int(status)!=1:raise ValueError('STEP reader status '+str(status))
    if not reader.Transfer(doc):raise ValueError('STEP transfer failed')
    tool=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main());free=TDF_LabelSequence();tool.GetFreeShapes(free)
    shapes=[]
    def walk(label,parent_location=TopLoc_Location(),names=()):
        nm=name_of(label)
        if tool.IsReference_s(label):
            referred=TDF_Label();tool.GetReferredShape_s(label,referred)
            location=parent_location.Multiplied(tool.GetLocation_s(label))
            walk(referred,location,names+(nm,))
        elif tool.IsAssembly_s(label):
            children=TDF_LabelSequence();tool.GetComponents_s(label,children,False)
            for i in range(1,children.Length()+1):walk(children.Value(i),parent_location,names+(nm,))
        else:
            wrapped=tool.GetShape_s(label).Moved(parent_location)
            if not wrapped.IsNull():
                shape=cq.Shape.cast(wrapped)
                shapes.append({'name':nm,'path':list(names+(nm,)),'shape':shape})
    for i in range(1,free.Length()+1):walk(free.Value(i))
    return shapes


def describe(record):
    s=record['shape']
    # Native get3DFile([]) can retain named but empty component groups. They
    # have a non-null TopoDS compound and a void bounding box, not a solid.
    empty=not s.Vertices()
    b=None if empty else s.BoundingBox()
    return {'name':record['name'],'path':record['path'],
            'bbox':None if b is None else [round(v,6) for v in [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]],
            'solid_count':len(s.Solids()),'empty_geometry':empty,
            'valid':s.isValid(),'volume_mm3':0.0 if empty else round(s.Volume(),6)}

if __name__=='__main__':
    src=Path(sys.argv[1]);out=Path(sys.argv[2]);shapes=read_named_shapes(src)
    result={'source':src.name,'bytes':src.stat().st_size,'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'units':'mm, as read from STEP','shapes':[describe(r) for r in shapes]}
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'source':src.name,'named_leaf_shapes':len(shapes),'report':str(out)}))
