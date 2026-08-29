from __future__ import annotations

from pathlib import Path
import math
from typing import Any, Callable

import ezdxf


LAYERS = {
    "L00_AUX": (8, 13),
    "L01_OUTER_CUT": (1, 35),
    "L02_INNER_CUT": (2, 25),
    "L10_GROOVE_FRONT": (3, 20),
    "L11_GROOVE_BACK": (5, 20),
    "L20_FACE_OUTER": (1, 20),
    "L21_GROOVE_OUTER": (6, 20),
    "L22_GROOVE_INNER": (4, 20),
    "L23_FACE_INNER": (3, 20),
    "L30_DIM": (6, 13),
    "L31_NOTE_CN": (7, 13),
    "L32_PART_ID": (2, 13),
}

OLD_LONG = 1740.0
OLD_SHORT_START = 7.0
OLD_SHORT_END = 1733.0

# Four independent source pieces. They are never software-mirrored.
GROUPS = [
    {
        "name": "上框骨架", "part": "top", "kind": "skeleton",
        "src_x0": 2465.5, "src_x1": 2754.5,
        "target_x": 350.0, "target_y": 100.0,
        "src_chain": [0, 13, 63, 186, 206, 276, 289],
        "source_front_dims": [(0, 166)],
        "source_grooves": [(13, "BACK"), (63, "BACK"), (166, "FRONT"), (186, "BACK"), (206, "BACK"), (276, "BACK")],
        "pin_x_source": 102.0,
        "outer_side": "left",
        "short_tab_range": (190.5, 198.5),
    },
    {
        "name": "下框骨架", "part": "bottom", "kind": "skeleton",
        "src_x0": 3545.5, "src_x1": 3834.5,
        "target_x": 1250.0, "target_y": 100.0,
        "src_chain": [0, 13, 83, 103, 226, 276, 289],
        "source_front_dims": [(123, 289)],
        "source_grooves": [(13, "BACK"), (83, "BACK"), (103, "BACK"), (123, "FRONT"), (226, "BACK"), (276, "BACK")],
        "pin_x_source": 187.0,
        "outer_side": "right",
        "short_tab_range": (90.5, 98.5),
    },
    {
        "name": "上框外皮", "part": "top", "kind": "outer",
        "src_x0": 4890.576315665818, "src_x1": 5214.776315665818,
        "target_x": 2700.0, "target_y": 100.0,
        "src_chain": [0, 14.5, 68.5, 186.7, 197.7, 233.7, 307.7, 324.2],
        "source_front_dims": [(0, 168.3), (168.3, 176.9)],
        "source_grooves": [(14.5, "BACK"), (68.5, "BACK"), (168.3, "FRONT"), (176.9, "FRONT"), (186.7, "BACK"), (197.7, "BACK"), (233.7, "BACK"), (307.7, "BACK")],
        "pin_x_source": 108.5,
        "outer_side": "left",
        "short_tab_range": None,
    },
    {
        "name": "下框外皮", "part": "bottom", "kind": "outer",
        "src_x0": 6007.5765, "src_x1": 6331.7765,
        "target_x": 3700.0, "target_y": 100.0,
        "src_chain": [0, 16.5, 90.5, 126.5, 137.5, 255.7, 309.7, 324.2],
        "source_front_dims": [(155.9, 324.2), (147.3, 155.9)],
        "source_grooves": [(16.5, "BACK"), (90.5, "BACK"), (126.5, "BACK"), (137.5, "BACK"), (147.3, "FRONT"), (155.9, "FRONT"), (255.7, "BACK"), (309.7, "BACK")],
        "pin_x_source": 215.7,
        "outer_side": "right",
        "short_tab_range": None,
    },
]


def _create_doc() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    for name, (color, lineweight) in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=color, lineweight=lineweight)
    if "CN_TEXT" not in doc.styles:
        doc.styles.new("CN_TEXT", dxfattribs={"font": "simsun.ttc"})
    if "NUM_TEXT" not in doc.styles:
        doc.styles.new("NUM_TEXT", dxfattribs={"font": "arial.ttf"})
    for style_name, height, arrow in [
        ("DIM_PLAN", 8.5, 4.0),
        ("DIM_SECTION", 4.8, 2.3),
        ("DIM_DETAIL", 3.3, 1.7),
    ]:
        if style_name not in doc.dimstyles:
            doc.dimstyles.new(style_name)
        ds = doc.dimstyles.get(style_name)
        ds.dxf.dimtxt = height
        ds.dxf.dimasz = arrow
        ds.dxf.dimexe = 1.5
        ds.dxf.dimexo = 0.7
        ds.dxf.dimgap = 1.0
        ds.dxf.dimclrd = 6
        ds.dxf.dimclre = 6
        ds.dxf.dimclrt = 7
        ds.dxf.dimdec = 1
        ds.dxf.dimzin = 8
        ds.dxf.dimtad = 1
        try:
            ds.dxf.dimtxsty = "NUM_TEXT"
        except Exception:
            pass
    return doc


def _add_text(msp, text: str, x: float, y: float, height: float = 8, width: float = 500, layer: str = "L31_NOTE_CN"):
    entity = msp.add_mtext(text, dxfattribs={"style": "CN_TEXT", "char_height": height, "width": width, "layer": layer})
    entity.set_location((x, y))
    return entity


def _add_hdim(msp, p1, p2, base_y: float, style: str = "DIM_SECTION") -> None:
    dim = msp.add_linear_dim(base=(p1[0], base_y), p1=p1, p2=p2, angle=0, dimstyle=style)
    dim.dimension.dxf.layer = "L30_DIM"
    dim.render()


def _add_vdim(msp, p1, p2, base_x: float, style: str = "DIM_SECTION") -> None:
    dim = msp.add_linear_dim(base=(base_x, p1[1]), p1=p1, p2=p2, angle=90, dimstyle=style)
    dim.dimension.dxf.layer = "L30_DIM"
    dim.render()


def _draw_three_row_horizontal_dimensions(
    msp, *, x0: float, datum_y: float, width: float,
    inner_points: list[float], outer_pairs: list[tuple[float,float]],
    inner_base_y: float, outer_base_y: float, total_base_y: float,
) -> None:
    """Common three-row annotation standard for flat sections and plans."""
    for a,b in zip(inner_points[:-1],inner_points[1:]):
        _add_hdim(msp,(x0+a,datum_y),(x0+b,datum_y),inner_base_y,"DIM_DETAIL")
    for a,b in outer_pairs:
        _add_hdim(msp,(x0+a,datum_y),(x0+b,datum_y),outer_base_y,"DIM_DETAIL")
    _add_hdim(msp,(x0,datum_y),(x0+width,datum_y),total_base_y,"DIM_PLAN")


def _add_line(msp, p1, p2, layer: str) -> None:
    msp.add_line(p1, p2, dxfattribs={"layer": layer})


def _add_center_rect(msp, cx: float, cy: float, width: float, height: float, layer: str = "L02_INNER_CUT") -> None:
    points = [(cx-width/2, cy-height/2), (cx+width/2, cy-height/2), (cx+width/2, cy+height/2), (cx-width/2, cy+height/2), (cx-width/2, cy-height/2)]
    msp.add_lwpolyline(points, dxfattribs={"layer": layer})


def _add_obround_vertical(msp, cx: float, cy: float, width: float, height: float, layer: str = "L02_INNER_CUT") -> None:
    radius = width/2
    straight_half = height/2-radius
    msp.add_arc((cx, cy+straight_half), radius, 0, 180, dxfattribs={"layer": layer})
    msp.add_arc((cx, cy-straight_half), radius, 180, 360, dxfattribs={"layer": layer})
    _add_line(msp, (cx-radius, cy-straight_half), (cx-radius, cy+straight_half), layer)
    _add_line(msp, (cx+radius, cy-straight_half), (cx+radius, cy+straight_half), layer)


def _line_intersection(a1, a2, b1, b2):
    x1,y1=a1; x2,y2=a2; x3,y3=b1; x4,y4=b2
    denominator=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    if abs(denominator)<1e-9:
        return a2
    px=((x1*y2-y1*x2)*(x3-x4)-(x1-x2)*(x3*y4-y3*x4))/denominator
    py=((x1*y2-y1*x2)*(y3-y4)-(y1-y2)*(x3*y4-y3*x4))/denominator
    return px,py


def _offset_open_polyline(points, distance: float):
    normals=[]
    for a,b in zip(points[:-1],points[1:]):
        dx=b[0]-a[0]; dy=b[1]-a[1]
        length=math.hypot(dx,dy)
        normals.append((-dy/length,dx/length))
    result=[]
    nx,ny=normals[0]
    result.append((points[0][0]+distance*nx,points[0][1]+distance*ny))
    for index in range(1,len(points)-1):
        n1=normals[index-1]; n2=normals[index]
        a1=(points[index-1][0]+distance*n1[0],points[index-1][1]+distance*n1[1])
        a2=(points[index][0]+distance*n1[0],points[index][1]+distance*n1[1])
        b1=(points[index][0]+distance*n2[0],points[index][1]+distance*n2[1])
        b2=(points[index+1][0]+distance*n2[0],points[index+1][1]+distance*n2[1])
        result.append(_line_intersection(a1,a2,b1,b2))
    nx,ny=normals[-1]
    result.append((points[-1][0]+distance*nx,points[-1][1]+distance*ny))
    return result


def calculate_top_bottom(door_width: float, side_small: float, side_large: float) -> dict[str,float]:
    door_width=float(door_width); side_small=float(side_small); side_large=float(side_large)
    if door_width<=0 or side_small<=0 or side_large<=0:
        raise ValueError("门宽和左右框宽度必须大于0。")
    if side_large<=side_small:
        raise ValueError("左右框大边必须大于小边。")
    long_length=door_width-side_small*2
    short_length=door_width-side_large*2
    if short_length<=0:
        raise ValueError("门宽不足，计算后的上下框短边长度小于等于0。")
    return {"long_length":long_length,"short_length":short_length,"protrusion":side_large-side_small,"pin_center":long_length/2-54}


def _new_chain(group: dict[str,Any], outer_short: float, outer_long: float) -> list[float]:
    if outer_short<=0 or outer_long<=outer_short:
        raise ValueError(f"{group['name']}尺寸必须满足大边大于小边。")
    if group["kind"]=="skeleton":
        sk_small=outer_short-3.0
        sk_large=outer_long-3.0
        if sk_small<=2 or sk_large<=2:
            raise ValueError(f"{group['name']}骨架尺寸过小。")
        if group["part"]=="top":
            segments=[13.0,sk_small-2.0,123.0,20.0,sk_large-2.0,13.0]
        else:
            segments=[13.0,sk_large-2.0,20.0,123.0,sk_small-2.0,13.0]
    else:
        if group["part"]=="top":
            segments=[14.5,outer_short-1.0,118.2,11.0,36.0,outer_long-1.0,16.5]
        else:
            segments=[16.5,outer_long-1.0,36.0,11.0,118.2,outer_short-1.0,14.5]
    chain=[0.0]
    for value in segments:
        chain.append(chain[-1]+value)
    return chain


def _piecewise_mapper(source_chain: list[float], target_chain: list[float]) -> Callable[[float],float]:
    def mapper(value: float) -> float:
        value=float(value)
        if value<=source_chain[0]:
            return target_chain[0]+(value-source_chain[0])
        if value>=source_chain[-1]:
            return target_chain[-1]+(value-source_chain[-1])
        for s0,s1,t0,t1 in zip(source_chain[:-1],source_chain[1:],target_chain[:-1],target_chain[1:]):
            if s0-1e-9<=value<=s1+1e-9:
                if abs(s1-s0)<1e-9:
                    return t0
                ratio=(value-s0)/(s1-s0)
                return t0+ratio*(t1-t0)
        return value
    return mapper


def _make_y_mapper(long_length: float, short_length: float, protrusion: float, group: dict[str,Any]):
    short_start=protrusion
    short_end=short_start+short_length
    short_tab_range=group.get("short_tab_range")

    def base_map(y: float) -> float:
        y=float(y)
        if y<0:
            return y
        if y<=OLD_SHORT_START:
            return y*(short_start/OLD_SHORT_START)
        if y<=OLD_SHORT_END:
            return short_start+(y-OLD_SHORT_START)*(short_length/(OLD_SHORT_END-OLD_SHORT_START))
        if y<=OLD_LONG:
            return short_end+(y-OLD_SHORT_END)*((long_length-short_end)/(OLD_LONG-OLD_SHORT_END))
        return long_length+(y-OLD_LONG)

    def mapper(x_relative: float, y: float) -> float:
        # The two narrow skeleton tabs are fixed at 8 mm. They do not scale
        # with the side-frame width difference. The wide central tab remains 13 mm.
        if group["kind"]=="skeleton" and short_tab_range and short_tab_range[0]-0.01<=x_relative<=short_tab_range[1]+0.01:
            if -1.01<=y<=OLD_SHORT_START+0.01:
                return short_start+(y-OLD_SHORT_START)  # 7 -> protrusion, -1 -> protrusion-8
            if OLD_SHORT_END-0.01<=y<=1741.01:
                return short_end+(y-OLD_SHORT_END)      # 1733 -> short end, 1741 -> +8
        return base_map(y)
    return mapper


def _in_group_x(x: float, group: dict[str,Any], margin: float=1.0) -> bool:
    return group["src_x0"]-margin<=x<=group["src_x1"]+margin


def _section_case(group: dict[str,Any], outer_short: float, outer_long: float, x_mapper: Callable[[float],float], target_chain: list[float]) -> dict[str,Any]:
    grooves=[(x_mapper(x),face) for x,face in group["source_grooves"]]
    front_dims=[(x_mapper(a),x_mapper(b)) for a,b in group["source_front_dims"]]
    if group["kind"]=="skeleton":
        small=outer_short-3.0; large=outer_long-3.0
        profile=[(0,0),(0,14),(small,14),(small,-88),(large,-88),(large,-111),(0,-111),(0,-97)]
        return {"name":group["name"],"kind":"skeleton","thickness":2.0,"depth":1.0,"groove_width":2.0,"flat_width":target_chain[-1],"grooves":grooves,"chain":target_chain,"front_dims":front_dims,"profile":profile}
    profile=[(0,0),(0,15),(outer_short,15),(outer_short,-85),(outer_short+8,-85),(outer_short+8,-75),(outer_long,-75),(outer_long,-112),(0,-112),(0,-95)]
    return {"name":group["name"],"kind":"outer","thickness":0.8,"depth":0.3,"groove_width":0.6,"flat_width":target_chain[-1],"grooves":grooves,"chain":target_chain,"front_dims":front_dims,"profile":profile}


def _draw_flat_section(msp, case: dict[str,Any], x0: float, y0: float) -> None:
    _add_text(msp,f"{case['name']}展开截面图",x0,y0+170,9.5,300)
    thickness=case["thickness"]; depth=case["depth"]; half=case["groove_width"]/2
    y_outer=y0+thickness/2; y_outer_depth=y_outer-depth
    y_inner=y0-thickness/2; y_inner_depth=y_inner+depth
    outer=[(x0,y_outer)]; inner=[(x0,y_inner)]
    for gx,face in case["grooves"]:
        if face=="FRONT":
            outer.extend([(x0+gx-half,y_outer),(x0+gx,y_outer_depth),(x0+gx+half,y_outer)])
        else:
            inner.extend([(x0+gx-half,y_inner),(x0+gx,y_inner_depth),(x0+gx+half,y_inner)])
    outer.append((x0+case["flat_width"],y_outer)); inner.append((x0+case["flat_width"],y_inner))
    msp.add_lwpolyline(outer,dxfattribs={"layer":"L20_FACE_OUTER"})
    _add_line(msp,(x0,y_outer_depth),(x0+case["flat_width"],y_outer_depth),"L21_GROOVE_OUTER")
    _add_line(msp,(x0,y_inner_depth),(x0+case["flat_width"],y_inner_depth),"L22_GROOVE_INNER")
    msp.add_lwpolyline(inner,dxfattribs={"layer":"L23_FACE_INNER"})
    _draw_three_row_horizontal_dimensions(
        msp,x0=x0,datum_y=y0,width=case["flat_width"],
        inner_points=case["chain"],outer_pairs=case["front_dims"],
        inner_base_y=y0-48,outer_base_y=y0+48,total_base_y=y0+94,
    )
    # Keep the thickness dimension on the LEFT side for every part, including
    # right-hand parts whose section coordinates are already reversed.
    _add_vdim(msp, (x0,y_inner), (x0,y_outer), x0-28, "DIM_DETAIL")


def _draw_folded_section(msp, case: dict[str,Any], center_x: float, y0: float, mirrored: bool=False) -> None:
    """Draw a four-line folded section with complete finished-size dimensions."""
    profile=case["profile"]
    depth1=_offset_open_polyline(profile,-case["depth"])
    depth2=_offset_open_polyline(profile,-(case["thickness"]-case["depth"]))
    inner=_offset_open_polyline(profile,-case["thickness"])
    all_points=profile+depth1+depth2+inner
    min_x=min(p[0] for p in all_points); max_x=max(p[0] for p in all_points); min_y=min(p[1] for p in all_points)
    dx=center_x-(min_x+max_x)/2; dy=y0-min_y
    shift=lambda pts:[(x+dx,y+dy) for x,y in pts]
    outer=shift(profile); depth1=shift(depth1); depth2=shift(depth2); inner=shift(inner)
    if mirrored:
        mirror=lambda pts:[(2*center_x-x,y) for x,y in pts]
        outer=mirror(outer); depth1=mirror(depth1); depth2=mirror(depth2); inner=mirror(inner)
    side_note="（右件镜像）" if mirrored else ""
    _add_text(msp,f"{case['name']}折弯截面图{side_note}",center_x-115,y0+275,9.5,300)
    _add_text(msp,"成品外轮廓尺寸直接取最外表线；折弯状态不显示V槽口。",center_x-170,y0+250,4.8,360)
    msp.add_lwpolyline(outer,dxfattribs={"layer":"L20_FACE_OUTER"})
    msp.add_lwpolyline(depth1,dxfattribs={"layer":"L21_GROOVE_OUTER"})
    msp.add_lwpolyline(depth2,dxfattribs={"layer":"L22_GROOVE_INNER"})
    msp.add_lwpolyline(inner,dxfattribs={"layer":"L23_FACE_INNER"})
    p=outer
    sign=-1 if mirrored else 1
    bx=lambda point,offset: point[0]+sign*offset
    if case["kind"]=="skeleton":
        # 52/72 family: top, bottom, total depth, 14/102/step/23/14.
        _add_hdim(msp,p[1],p[2],p[1][1]+42,"DIM_SECTION")
        _add_hdim(msp,p[6],p[5],p[6][1]-42,"DIM_SECTION")
        _add_vdim(msp,p[1],p[5],bx(p[5],132),"DIM_PLAN")
        _add_vdim(msp,p[0],p[1],bx(p[0],-34),"DIM_DETAIL")
        _add_vdim(msp,p[2],p[3],bx(p[2],45),"DIM_SECTION")
        _add_hdim(msp,p[3],p[4],p[3][1]+32,"DIM_DETAIL")
        _add_vdim(msp,p[4],p[5],bx(p[4],80),"DIM_SECTION")
        _add_vdim(msp,p[6],p[7],bx(p[6],-34),"DIM_DETAIL")
    else:
        # 55/75 family: top, bottom, total depth, 15/100/8/10/12/37/17.
        _add_hdim(msp,p[1],p[2],p[1][1]+42,"DIM_SECTION")
        _add_hdim(msp,p[8],p[7],p[8][1]-42,"DIM_SECTION")
        _add_vdim(msp,p[1],p[7],bx(p[7],184),"DIM_PLAN")
        _add_vdim(msp,p[0],p[1],bx(p[0],-34),"DIM_DETAIL")
        _add_vdim(msp,p[2],p[3],bx(p[2],45),"DIM_SECTION")
        _add_hdim(msp,p[3],p[4],p[3][1]+30,"DIM_DETAIL")
        _add_vdim(msp,p[4],p[5],bx(p[4],75),"DIM_DETAIL")
        _add_hdim(msp,p[5],p[6],p[5][1]+40,"DIM_DETAIL")
        _add_vdim(msp,p[6],p[7],bx(p[6],110),"DIM_SECTION")
        _add_vdim(msp,p[8],p[9],bx(p[8],-34),"DIM_DETAIL")


def _add_plan_dimensions(msp, group: dict[str,Any], lengths: dict[str,float], width: float, chain: list[float], front_dims: list[tuple[float,float]]) -> None:
    x0=group["target_x"]; y0=group["target_y"]
    long_length=lengths["long_length"]; short_length=lengths["short_length"]; protrusion=lengths["protrusion"]
    short_bottom=y0+protrusion; short_top=short_bottom+short_length; top=y0+long_length

    # Unified plan standard: all three horizontal rows above the plan.
    _draw_three_row_horizontal_dimensions(
        msp,x0=x0,datum_y=top,width=width,
        inner_points=chain,outer_pairs=front_dims,
        inner_base_y=top+40,outer_base_y=top+86,total_base_y=top+134,
    )

    pin_description="34.5×38方孔" if group["kind"]=="skeleton" else "35.5×72.5长圆孔"
    _add_text(msp,group["name"],x0,top+215,10.5,280,"L32_PART_ID")
    _add_text(msp,f"长边{long_length:.0f}；短边{short_length:.0f}；端差{protrusion:.0f}；小凸出8/8；宽凸出13；插销孔{pin_description}。",x0,top+184,5.0,430)
    if group["outer_side"]=="left":
        _add_vdim(msp,(x0,y0),(x0,y0+long_length),x0-68,"DIM_PLAN")
        _add_vdim(msp,(x0+width,short_bottom),(x0+width,short_top),x0+width+68,"DIM_PLAN")
        _add_vdim(msp,(x0+width,y0),(x0+width,short_bottom),x0+width+98,"DIM_DETAIL")
    else:
        _add_vdim(msp,(x0+width,y0),(x0+width,y0+long_length),x0+width+68,"DIM_PLAN")
        _add_vdim(msp,(x0,short_bottom),(x0,short_top),x0-68,"DIM_PLAN")
        _add_vdim(msp,(x0,y0),(x0,short_bottom),x0-98,"DIM_DETAIL")


def _copy_source_piece(msp, source_msp, group: dict[str,Any], lengths: dict[str,float], outer_short: float, outer_long: float, *, include_pin: bool) -> dict[str,Any]:
    source_x0=group["src_x0"]; target_x=group["target_x"]; target_y=group["target_y"]
    target_chain=_new_chain(group,outer_short,outer_long)
    x_mapper=_piecewise_mapper(group["src_chain"],target_chain)
    y_mapper=_make_y_mapper(lengths["long_length"],lengths["short_length"],lengths["protrusion"],group)
    for entity in source_msp:
        etype=entity.dxftype()
        if etype=="LINE":
            x1,y1,_=entity.dxf.start; x2,y2,_=entity.dxf.end
            if not (_in_group_x(x1,group) and _in_group_x(x2,group)): continue
            if min(y1,y2)<-30 or max(y1,y2)>1770: continue
            if entity.dxf.layer not in ("0","标注层"): continue
            layer=("L10_GROOVE_FRONT" if int(entity.dxf.color)==6 else "L11_GROOVE_BACK") if entity.dxf.layer=="标注层" else "L01_OUTER_CUT"
            rx1=float(x1-source_x0); rx2=float(x2-source_x0)
            _add_line(msp,(target_x+x_mapper(rx1),target_y+y_mapper(rx1,y1)),(target_x+x_mapper(rx2),target_y+y_mapper(rx2,y2)),layer)
        elif etype=="ARC":
            cx,cy,_=entity.dxf.center; radius=float(entity.dxf.radius)
            if not _in_group_x(cx,group): continue
            if cy-radius<-30 or cy+radius>1770 or entity.dxf.layer!="0": continue
            rcx=float(cx-source_x0)
            msp.add_arc((target_x+x_mapper(rcx),target_y+y_mapper(rcx,cy)),radius,float(entity.dxf.start_angle),float(entity.dxf.end_angle),dxfattribs={"layer":"L01_OUTER_CUT"})
    width=target_chain[-1]
    # Long and short sides use their own actual end boundaries.  Therefore the
    # two end fixing holes are intentionally not horizontally aligned.
    long_x = 6.0 if group["outer_side"]=="left" else width-6.0
    short_x = width-6.0 if group["outer_side"]=="left" else 6.0
    long_positions = (30.0, lengths["long_length"]/2, lengths["long_length"]-30.0)
    short_start = lengths["protrusion"]
    short_end = short_start + lengths["short_length"]
    short_positions = (short_start+30.0, (short_start+short_end)/2, short_end-30.0)
    for relative_x, positions in ((long_x,long_positions),(short_x,short_positions)):
        for yy in positions:
            if group["kind"]=="skeleton":
                msp.add_circle((target_x+relative_x,target_y+yy),2.25,dxfattribs={"layer":"L02_INNER_CUT"})
            else:
                _add_obround_vertical(msp,target_x+relative_x,target_y+yy,5.0,9.0)
    if include_pin:
        pin_x=x_mapper(group["pin_x_source"])
        pin_y=lengths["pin_center"]
        if group["kind"]=="skeleton": _add_center_rect(msp,target_x+pin_x,target_y+pin_y,34.5,38.0)
        else: _add_obround_vertical(msp,target_x+pin_x,target_y+pin_y,35.5,72.5)
    front_dims=[(x_mapper(a),x_mapper(b)) for a,b in group["source_front_dims"]]
    _add_plan_dimensions(msp,group,lengths,width,target_chain,front_dims)
    return {"target_chain":target_chain,"width":width,"x_mapper":x_mapper,"section":_section_case(group,outer_short,outer_long,x_mapper,target_chain)}


def draw_top_bottom_layout(
    msp,
    *,
    source_template: str|Path,
    door_width: float,
    side_small: float,
    side_large: float,
    top_outer_short: float=55.0,
    top_outer_long: float=75.0,
    bottom_outer_short: float=55.0,
    bottom_outer_long: float=75.0,
    include_top: bool=True,
    include_bottom: bool=True,
    top_pin: bool=True,
    bottom_pin: bool=True,
    origin_x: float=0.0,
    origin_y: float=0.0,
    show_title: bool=True,
) -> dict[str,Any]:
    if not include_top and not include_bottom:
        raise ValueError("上框和下框至少选择一个。")
    for label,small,large in (("上框",top_outer_short,top_outer_long),("下框",bottom_outer_short,bottom_outer_long)):
        if small<=0 or large<=small:
            raise ValueError(f"{label}必须满足大边大于小边，且尺寸大于0。")
    lengths=calculate_top_bottom(door_width,side_small,side_large)
    source_template=Path(source_template)
    if not source_template.exists():
        raise FileNotFoundError(f"上下框模板不存在：{source_template}")
    source_doc=ezdxf.readfile(source_template); source_msp=source_doc.modelspace()

    if show_title:
        _add_text(msp,f"上下框参数化生产图｜门宽{door_width:.0f}｜左右框{side_small:.0f}/{side_large:.0f}｜上框{top_outer_short:.0f}/{top_outer_long:.0f}｜下框{bottom_outer_short:.0f}/{bottom_outer_long:.0f}",origin_x+70,origin_y+3300,16,1600)
        _add_text(msp,"统一三行标注：内侧报槽、外侧报槽、展开总长；展开截面下侧为内槽、上侧为外槽和总长，展开平面三行均放在图形上侧。长边和短边固定孔分别按各自边界定位。",origin_x+70,origin_y+3265,6.5,1700)
    msp.add_line((origin_x+2325,origin_y+50),(origin_x+2325,origin_y+3200),dxfattribs={"layer":"L00_AUX"})
    _add_text(msp,"左区：上下框骨架",origin_x+90,origin_y+3205,13,500)
    _add_text(msp,"右区：上下框外皮",origin_x+2440,origin_y+3205,13,500)

    results=[]
    for base_group in GROUPS:
        if base_group["part"]=="top" and not include_top:
            continue
        if base_group["part"]=="bottom" and not include_bottom:
            continue
        group=dict(base_group)
        group["target_x"]=origin_x+base_group["target_x"]
        group["target_y"]=origin_y+base_group["target_y"]
        outer_short,outer_long=(top_outer_short,top_outer_long) if group["part"]=="top" else (bottom_outer_short,bottom_outer_long)
        include_pin=top_pin if group["part"]=="top" else bottom_pin
        item=_copy_source_piece(msp,source_msp,group,lengths,outer_short,outer_long,include_pin=include_pin)
        center_x=group["target_x"]+item["width"]/2
        _draw_flat_section(msp,item["section"],group["target_x"],origin_y+2440)
        _draw_folded_section(msp,item["section"],center_x,origin_y+2790,mirrored=(group["outer_side"]=="right"))
        results.append({"name":group["name"],"width":item["width"],"outer":[outer_short,outer_long]})
    return {
        **lengths,
        "parts":results,
        "include_top":include_top,
        "include_bottom":include_bottom,
        "drawing_width":4300.0,
        "drawing_height":3370.0,
    }


def generate_top_bottom_dxf(output_path: str|Path, *, source_template: str|Path, door_width: float, side_small: float, side_large: float, top_outer_short: float=55.0, top_outer_long: float=75.0, bottom_outer_short: float=55.0, bottom_outer_long: float=75.0, include_top: bool=True, include_bottom: bool=True, top_pin: bool=True, bottom_pin: bool=True) -> dict[str,Any]:
    doc=_create_doc(); msp=doc.modelspace()
    result=draw_top_bottom_layout(
        msp,
        source_template=source_template,
        door_width=door_width,
        side_small=side_small,
        side_large=side_large,
        top_outer_short=top_outer_short,
        top_outer_long=top_outer_long,
        bottom_outer_short=bottom_outer_short,
        bottom_outer_long=bottom_outer_long,
        include_top=include_top,
        include_bottom=include_bottom,
        top_pin=top_pin,
        bottom_pin=bottom_pin,
        origin_x=0,
        origin_y=0,
        show_title=True,
    )
    output_path=Path(output_path); output_path.parent.mkdir(parents=True,exist_ok=True); doc.saveas(output_path)
    auditor=ezdxf.readfile(output_path).audit()
    return {"output":str(output_path),**result,"audit_errors":len(auditor.errors),"audit_fixes":len(auditor.fixes)}

