
from pathlib import Path
import math
import ezdxf

HEIGHT_DEFAULT = 2730.0

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
    "L33_CENTER_MARK": (4, 13),
}

# =========================
# Geometry helpers
# =========================
def line_intersection(a1, a2, b1, b2):
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2
    den = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(den) < 1e-9:
        return a2
    px = ((x1*y2-y1*x2)*(x3-x4) - (x1-x2)*(x3*y4-y3*x4)) / den
    py = ((x1*y2-y1*x2)*(y3-y4) - (y1-y2)*(x3*y4-y3*x4)) / den
    return (px, py)

def offset_open_polyline(points, distance):
    normals = []
    for i in range(len(points)-1):
        x1, y1 = points[i]
        x2, y2 = points[i+1]
        dx, dy = x2-x1, y2-y1
        length = math.hypot(dx, dy)
        normals.append((-dy/length, dx/length))
    out = []
    nx, ny = normals[0]
    out.append((points[0][0] + distance*nx, points[0][1] + distance*ny))
    for i in range(1, len(points)-1):
        nx1, ny1 = normals[i-1]
        nx2, ny2 = normals[i]
        a1 = (points[i-1][0] + distance*nx1, points[i-1][1] + distance*ny1)
        a2 = (points[i][0] + distance*nx1, points[i][1] + distance*ny1)
        b1 = (points[i][0] + distance*nx2, points[i][1] + distance*ny2)
        b2 = (points[i+1][0] + distance*nx2, points[i+1][1] + distance*ny2)
        out.append(line_intersection(a1, a2, b1, b2))
    nx, ny = normals[-1]
    out.append((points[-1][0] + distance*nx, points[-1][1] + distance*ny))
    return out

def shift(points, dx, dy):
    return [(x+dx, y+dy) for x, y in points]

def add_rect(msp, x1, y1, x2, y2, layer):
    msp.add_lwpolyline([(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)], dxfattribs={"layer": layer})

def add_center_rect(msp, cx, cy, width, height, layer):
    add_rect(msp, cx-width/2, cy-height/2, cx+width/2, cy+height/2, layer)

def add_circle(msp, cx, cy, diameter, layer):
    msp.add_circle((cx, cy), diameter/2, dxfattribs={"layer": layer})

def add_obround_vertical(msp, cx, cy, width, height, layer):
    radius = width/2
    straight_half = height/2 - radius
    msp.add_arc((cx, cy+straight_half), radius, 0, 180, dxfattribs={"layer": layer})
    msp.add_arc((cx, cy-straight_half), radius, 180, 360, dxfattribs={"layer": layer})
    msp.add_line((cx-radius, cy-straight_half), (cx-radius, cy+straight_half), dxfattribs={"layer": layer})
    msp.add_line((cx+radius, cy-straight_half), (cx+radius, cy+straight_half), dxfattribs={"layer": layer})

def add_cn_mtext(msp, text, x, y, height=8, width=350, layer="L31_NOTE_CN"):
    ent = msp.add_mtext(text, dxfattribs={"style":"CN_TEXT","char_height":height,"layer":layer,"width":width})
    ent.set_location((x,y))
    return ent

def add_hdim(msp, p1, p2, base_y, style="DIM_SECTION"):
    dim = msp.add_linear_dim(base=(p1[0], base_y), p1=p1, p2=p2, angle=0, dimstyle=style)
    dim.dimension.dxf.layer = "L30_DIM"
    dim.render()

def add_vdim(msp, p1, p2, base_x, style="DIM_SECTION"):
    dim = msp.add_linear_dim(base=(base_x, p1[1]), p1=p1, p2=p2, angle=90, dimstyle=style)
    dim.dimension.dxf.layer = "L30_DIM"
    dim.render()

def mirror_x(x, total_width):
    return total_width - x


def _standard_groove_dimensions(case, mirrored=False):
    """Return standardized inner-chain and outer-groove dimension endpoints.

    Standard used by both flat sections and unfolded plans:
    - inner/back grooves are a continuous chain between the two sheet edges;
    - outer/front grooves are located from the functional reference edge;
    - the same endpoints are mirrored for right-hand parts.
    """
    width = float(case["flat_width"])
    back_positions = [
        float(x) for x, face in zip(case["groove_positions"], case["groove_faces"])
        if face == "BACK"
    ]
    front_positions = [
        float(x) for x, face in zip(case["groove_positions"], case["groove_faces"])
        if face == "FRONT"
    ]
    inner_points = [0.0] + back_positions + [width]
    # Original left/right-frame standard: first front groove from reference edge;
    # multiple front grooves then use their mutual spacing.
    outer_pairs = []
    if front_positions:
        outer_pairs.append((0.0, front_positions[0]))
        for a, b in zip(front_positions[:-1], front_positions[1:]):
            outer_pairs.append((a, b))
    if mirrored:
        inner_points = [width - x for x in reversed(inner_points)]
        outer_pairs = [(width-b, width-a) for a,b in outer_pairs]
    return inner_points, outer_pairs


def _draw_three_row_horizontal_dimensions(
    msp, *, x0, datum_y, width, inner_points, outer_pairs,
    inner_base_y, outer_base_y, total_base_y,
):
    """Draw exactly three standardized horizontal dimension rows."""
    for a, b in zip(inner_points[:-1], inner_points[1:]):
        add_hdim(msp, (x0+a, datum_y), (x0+b, datum_y), inner_base_y, "DIM_DETAIL")
    for a, b in outer_pairs:
        add_hdim(msp, (x0+a, datum_y), (x0+b, datum_y), outer_base_y, "DIM_DETAIL")
    add_hdim(msp, (x0, datum_y), (x0+width, datum_y), total_base_y, "DIM_PLAN")

# =========================
# Parametric cases
# =========================

def edge_fixing_positions(height, end_margin=15.0, max_spacing=540.0):
    """固定孔：上下端各一个，中间均布，任意相邻孔距不大于 max_spacing。

    2730 高度时复原原始孔位：15、555、1095、1635、2175、2715。
    """
    height=float(height); end_margin=float(end_margin); max_spacing=float(max_spacing)
    if height <= 2*end_margin:
        return [height/2.0]
    usable=height-2*end_margin
    segments=max(1, math.ceil(usable/max_spacing))
    spacing=usable/segments
    return [round(end_margin+i*spacing, 4) for i in range(segments+1)]

def _resolve_hinge_positions(height, hinge_count=3, hinge_layout="standard", hinge_positions=None):
    """Return hinge center distances from top edge in mm."""
    if hinge_positions:
        vals = []
        for v in hinge_positions:
            try:
                f = float(v)
            except Exception:
                continue
            if 0 < f < height:
                vals.append(round(f, 3))
        if vals:
            return sorted(vals)
    # standard templates
    if int(hinge_count) <= 3:
        return [280.0, 680.0, max(780.0, height - 280.0)]
    return [280.0, 680.0, height/2.0, max(height/2.0+250.0, height - 280.0)]

def make_outer_case(short_top=55.0, long_bottom=62.0, height=2700.0, thickness=0.8, groove_depth=0.3, groove_width=0.6, hinge_style="可拆卸合页", hinge_count=3, hinge_center_override=None, hinge_positions=None):
    """新工艺外皮：按用户确认DXF的展开平面图重建。"""
    delta = short_top - 55.0
    bottom_delta = long_bottom - 62.0

    # 55/62确认样本：展开宽324.8。
    # 反面槽：14.5、68.5、126.5、200.3、211.3、247.3、308.3
    # 正面槽：139.3、181.9、190.5
    plan_segments = [14.5, 54.0+delta, 58.0, 12.8, 42.6, 8.6, 9.8, 11.0, 36.0, 61.0+bottom_delta, 16.5]
    groove_faces = ["BACK","BACK","BACK","FRONT","FRONT","FRONT","BACK","BACK","BACK","BACK"]
    run=0.0; groove_positions=[]
    for seg in plan_segments[:-1]:
        run += seg
        groove_positions.append(round(run,4))

    outer_profile=[
        (0.0,0.0),(0.0,15.0),(short_top,15.0),(short_top,-44.0),
        (short_top-13.0,-44.0),(short_top-13.0,-86.0),
        (short_top-5.0,-86.0),(short_top-5.0,-76.0),
        (long_bottom,-76.0),(long_bottom,-113.0),(0.0,-113.0),(0.0,-96.0),
    ]
    center = float(hinge_center_override) if hinge_center_override is not None else 98.5 + delta
    return {
        "name":"外皮（新工艺）","height":height,"thickness":thickness,
        "groove_depth":groove_depth,"groove_width":groove_width,
        "short_top":short_top,"long_bottom":long_bottom,"base_short":55.0,
        "base_hinge_center":98.5,"hinge_center_from_function_edge":center,
        "outer_profile":outer_profile,"plan_segments":plan_segments,
        "flat_width":round(sum(plan_segments),4),"groove_positions":groove_positions,"groove_faces":groove_faces,
        "hinge_shape":"OBROUND","hinge_rect_w":46.0,"hinge_rect_h":190.0,"hinge_radius":23.0,
        "edge_hole_shape":"OBROUND","edge_slot_w":5.0,"edge_slot_h":9.0,"edge_slot_x":6.0,
        "edge_slot_y":edge_fixing_positions(height),
        "hinge_from_top":_resolve_hinge_positions(height,hinge_count=hinge_count,hinge_positions=hinge_positions),
        "hinge_count":int(hinge_count),"hinge_style":hinge_style,
        "end_hole_d":0.0,"end_hole_x":[],"top_hole_from_top":29.7,"bottom_hole_from_bottom":29.7,
        "small_slot_w":20.0,"small_slot_h":3.75,"small_slot_x":[95.5+delta,232.8+delta+bottom_delta],
        "top_slot_from_top":[52.325,72.325],"bottom_slot_from_bottom":[52.325,72.325],
        "end_notch_x":[76.0+delta,239.8+delta+bottom_delta],"end_notch_depth":47.0,
    }

def make_skeleton_case(short_top=52.0, long_bottom=59.0, height=2700.0, thickness=2.0, groove_depth=1.0, groove_width=2.0, hinge_style="可拆卸合页", hinge_count=3, hinge_center_override=None, hinge_positions=None):
    """新工艺骨架：按用户确认DXF的展开平面图重建。"""
    delta=short_top-52.0
    bottom_delta=long_bottom-59.0

    # 52/59确认样本：展开宽289。
    # 反面槽：13、63、113、198、219、276
    # 正面槽：126、178
    plan_segments=[13.0,50.0+delta,50.0,13.0,52.0,20.0,21.0,57.0+bottom_delta,13.0]
    groove_faces=["BACK","BACK","BACK","FRONT","FRONT","BACK","BACK","BACK"]
    run=0.0; groove_positions=[]
    for seg in plan_segments[:-1]:
        run += seg
        groove_positions.append(round(run,4))

    outer_profile=[
        (0.0,0.0),(0.0,14.0),(short_top,14.0),(short_top,-38.0),
        (short_top-13.0,-38.0),(short_top-13.0,-88.0),
        (long_bottom,-88.0),(long_bottom,-111.0),(0.0,-111.0),(0.0,-97.0),
    ]
    center=float(hinge_center_override) if hinge_center_override is not None else 97.0+delta
    return {
        "name":"骨架（新工艺）","height":height,"thickness":thickness,
        "groove_depth":groove_depth,"groove_width":groove_width,
        "short_top":short_top,"long_bottom":long_bottom,"base_short":52.0,
        "base_hinge_center":97.0,"hinge_center_from_function_edge":center,
        "outer_profile":outer_profile,"plan_segments":plan_segments,
        "flat_width":round(sum(plan_segments),4),"groove_positions":groove_positions,"groove_faces":groove_faces,
        "hinge_shape":"SKELETON_COMPOUND","hinge_rect_w":68.0,"hinge_rect_h":192.0,
        "hinge_inner_holes":[(0.0,83.0,6.0),(0.0,-78.0,16.0)],
        "edge_hole_shape":"CIRCLE","edge_slot_w":4.5,"edge_slot_h":4.5,"edge_slot_x":6.0,
        "edge_slot_y":edge_fixing_positions(height),
        "hinge_from_top":_resolve_hinge_positions(height,hinge_count=hinge_count,hinge_positions=hinge_positions),
        "hinge_count":int(hinge_count),"hinge_style":hinge_style,
        "end_hole_d":9.0,"end_hole_x":[88.0+delta,151.0+delta,207.5+delta+bottom_delta],
        "top_hole_from_top":29.7,"bottom_hole_from_bottom":29.7,
        "small_slot_w":15.0,"small_slot_h":2.5,"small_slot_x":[88.0+delta,207.5+delta+bottom_delta],
        "top_slot_from_top":[52.95,72.95],"bottom_slot_from_bottom":[52.95,72.95],
        "end_notch_x":[],"end_notch_depth":0.0,
    }

# =========================
# Drawing helpers
# =========================
def create_doc():
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    for name, (color, lineweight) in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=color, lineweight=lineweight)

    if "CN_TEXT" not in doc.styles:
        doc.styles.new("CN_TEXT", dxfattribs={"font":"simsun.ttc"})
    if "NUM_TEXT" not in doc.styles:
        doc.styles.new("NUM_TEXT", dxfattribs={"font":"arial.ttf"})

    for style_name, text_height, arrow_size in [("DIM_PLAN",11.0,5.5),("DIM_SECTION",5.0,2.5),("DIM_DETAIL",4.0,2.0)]:
        if style_name not in doc.dimstyles:
            doc.dimstyles.new(style_name)
        ds = doc.dimstyles.get(style_name)
        ds.dxf.dimtxt = text_height
        ds.dxf.dimasz = arrow_size
        ds.dxf.dimexe = 1.8
        ds.dxf.dimexo = 0.8
        ds.dxf.dimgap = 1.2
        ds.dxf.dimclrd = 6
        ds.dxf.dimclre = 6
        ds.dxf.dimclrt = 7
        ds.dxf.dimdec = 1
        ds.dxf.dimzin = 8
        ds.dxf.dimtad = 1
        ds.dxf.dimjust = 0
        try:
            ds.dxf.dimtxsty = "NUM_TEXT"
        except Exception:
            pass
    return doc

def _mirror_points_x(points, axis_x):
    return [(2*axis_x-x, y) for x,y in points]


def draw_flat_section(msp, case, x0, y0, mirrored=False):
    side_note = "（右件镜像）" if mirrored else ""
    add_cn_mtext(msp, f"{case['name']}展开截面图{side_note}", x0, y0+170, height=12, width=320)
    add_cn_mtext(
        msp,
        f"板厚{case['thickness']}；槽宽{case['groove_width']}；槽深{case['groove_depth']}。",
        x0, y0+142, height=6, width=340,
    )

    width = case["flat_width"]
    y_outer = y0 + case["thickness"]/2
    y_outer_depth = y_outer - case["groove_depth"]
    y_inner = y0 - case["thickness"]/2
    y_inner_depth = y_inner + case["groove_depth"]
    half_groove = case["groove_width"] / 2

    outer_pts = [(x0, y_outer)]
    inner_pts = [(x0, y_inner)]
    for gx, face in zip(case["groove_positions"], case["groove_faces"]):
        xx = x0 + gx
        if face == "FRONT":
            outer_pts.extend([(xx-half_groove, y_outer), (xx, y_outer_depth), (xx+half_groove, y_outer)])
        else:
            inner_pts.extend([(xx-half_groove, y_inner), (xx, y_inner_depth), (xx+half_groove, y_inner)])
    outer_pts.append((x0+width, y_outer))
    inner_pts.append((x0+width, y_inner))

    if mirrored:
        axis=x0+width/2
        outer_pts=_mirror_points_x(outer_pts,axis)
        inner_pts=_mirror_points_x(inner_pts,axis)

    msp.add_lwpolyline(outer_pts, dxfattribs={"layer":"L20_FACE_OUTER"})
    msp.add_line((x0,y_outer_depth),(x0+width,y_outer_depth), dxfattribs={"layer":"L21_GROOVE_OUTER"})
    msp.add_line((x0,y_inner_depth),(x0+width,y_inner_depth), dxfattribs={"layer":"L22_GROOVE_INNER"})
    msp.add_lwpolyline(inner_pts, dxfattribs={"layer":"L23_FACE_INNER"})
    msp.add_line((x0,y_inner),(x0,y_outer), dxfattribs={"layer":"L00_AUX"})
    msp.add_line((x0+width,y_inner),(x0+width,y_outer), dxfattribs={"layer":"L00_AUX"})

    inner_points, outer_pairs = _standard_groove_dimensions(case, mirrored=mirrored)
    _draw_three_row_horizontal_dimensions(
        msp, x0=x0, datum_y=y0, width=width,
        inner_points=inner_points, outer_pairs=outer_pairs,
        inner_base_y=y0-48, outer_base_y=y0+48, total_base_y=y0+94,
    )
    # Thickness dimensions are standardized on the LEFT side of the flat section,
    # regardless of whether the part geometry is mirrored.
    thickness_dim_x = x0 - 28
    add_vdim(msp, (x0,y_inner), (x0,y_outer), thickness_dim_x, "DIM_DETAIL")


def draw_folded_section(msp, case, x0, y0, mirrored=False):
    side_note = "（右件镜像）" if mirrored else ""
    add_cn_mtext(msp, f"{case['name']}折弯截面图{side_note}", x0, y0+255, height=12, width=320)
    add_cn_mtext(msp, "折弯成品仅显示四条连续线：外表线、正面槽深线、反面槽深线、内表线。",
                 x0, y0+223, height=5.6, width=460)

    outer_local = case["outer_profile"]
    outer_face = outer_local
    outer_depth = offset_open_polyline(outer_local, -case["groove_depth"])
    inner_depth = offset_open_polyline(outer_local, -(case["thickness"] - case["groove_depth"]))
    inner_face = offset_open_polyline(outer_local, -case["thickness"])

    all_pts = outer_face + outer_depth + inner_depth + inner_face
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    dx, dy = x0 - min_x, y0 - min_y
    outer_face = shift(outer_face, dx, dy)
    outer_depth = shift(outer_depth, dx, dy)
    inner_depth = shift(inner_depth, dx, dy)
    inner_face = shift(inner_face, dx, dy)

    if mirrored:
        axis=x0+(max_x-min_x)/2
        outer_face=_mirror_points_x(outer_face,axis)
        outer_depth=_mirror_points_x(outer_depth,axis)
        inner_depth=_mirror_points_x(inner_depth,axis)
        inner_face=_mirror_points_x(inner_face,axis)

    msp.add_lwpolyline(outer_face, dxfattribs={"layer":"L20_FACE_OUTER"})
    msp.add_lwpolyline(outer_depth, dxfattribs={"layer":"L21_GROOVE_OUTER"})
    msp.add_lwpolyline(inner_depth, dxfattribs={"layer":"L22_GROOVE_INNER"})
    msp.add_lwpolyline(inner_face, dxfattribs={"layer":"L23_FACE_INNER"})
    msp.add_line(outer_face[0], inner_face[0], dxfattribs={"layer":"L00_AUX"})
    msp.add_line(outer_face[-1], inner_face[-1], dxfattribs={"layer":"L00_AUX"})

    p = outer_face
    sign=-1 if mirrored else 1
    def bx(point, offset):
        return point[0]+sign*offset

    is_outer = ("外皮" in case.get("name", "")) or (len(p) >= 11)
    if is_outer:
        add_hdim(msp, p[1], p[2], p[1][1]+42, "DIM_SECTION")
        add_hdim(msp, p[3], p[4], p[3][1]+22, "DIM_DETAIL")
        add_hdim(msp, p[5], p[6], p[5][1]+22, "DIM_DETAIL")
        add_hdim(msp, p[7], p[8], p[7][1]+22, "DIM_DETAIL")
        add_hdim(msp, p[10], p[9], p[10][1]-42, "DIM_SECTION")
        add_vdim(msp, p[0], p[1], bx(p[0], -34), "DIM_DETAIL")
        add_vdim(msp, p[10], p[11], bx(p[10], -34), "DIM_DETAIL")
        add_vdim(msp, p[2], p[3], bx(p[2], 42), "DIM_SECTION")
        add_vdim(msp, p[4], p[5], bx(p[4], 76), "DIM_SECTION")
        add_vdim(msp, p[6], p[7], bx(p[6], 110), "DIM_DETAIL")
        add_vdim(msp, p[8], p[9], bx(p[8], 144), "DIM_SECTION")
        add_vdim(msp, p[1], p[9], bx(p[9], 188), "DIM_PLAN")
    else:
        add_hdim(msp, p[1], p[2], p[1][1]+42, "DIM_SECTION")
        add_hdim(msp, p[3], p[4], p[3][1]+22, "DIM_DETAIL")
        add_hdim(msp, p[8], p[7], p[8][1]-40, "DIM_SECTION")
        add_vdim(msp, p[0], p[1], bx(p[0], -34), "DIM_DETAIL")
        add_vdim(msp, p[8], p[9], bx(p[8], -34), "DIM_DETAIL")
        add_vdim(msp, p[2], p[3], bx(p[2], 42), "DIM_SECTION")
        add_vdim(msp, p[4], p[5], bx(p[4], 78), "DIM_SECTION")
        add_vdim(msp, p[6], p[7], bx(p[6], 114), "DIM_SECTION")
        add_vdim(msp, p[1], p[7], bx(p[7], 158), "DIM_PLAN")

def draw_hinge_detail(msp, case, x0, y0):
    title=f"{case['name']}单组合页避让孔示意图"
    add_cn_mtext(msp,title,x0,y0+305,height=11,width=420)
    add_cn_mtext(
        msp,
        f"{case.get('hinge_style','合页')}｜数量{case.get('hinge_count',len(case['hinge_from_top']))}个\\P"
        f"中心横向距功能边 {case['hinge_center_from_function_edge']:.1f}",
        x0,y0+274,height=5.2,width=430,
    )
    cx=x0+140
    cy=y0+130
    shape=case.get("hinge_shape","RECT")
    if shape=="OBROUND":
        add_obround_vertical(msp,cx,cy,case["hinge_rect_w"],case["hinge_rect_h"],"L02_INNER_CUT")
        add_cn_mtext(msp,f"{case['hinge_rect_w']:.0f}×{case['hinge_rect_h']:.0f}｜R{case.get('hinge_radius',case['hinge_rect_w']/2):.0f}",x0+235,y0+155,height=5.2,width=180)
    else:
        add_center_rect(msp,cx,cy,case["hinge_rect_w"],case["hinge_rect_h"],"L02_INNER_CUT")
        for dx,dy,dia in case.get("hinge_inner_holes",[]):
            add_circle(msp,cx+dx,cy+dy,dia,"L02_INNER_CUT")
        add_cn_mtext(msp,f"外框 {case['hinge_rect_w']:.0f}×{case['hinge_rect_h']:.0f}\\P上孔 φ6，距中心+83\\P下孔 φ16，距中心-78",x0+235,y0+190,height=4.8,width=210)
    msp.add_line((cx,y0-15),(cx,y0+260),dxfattribs={"layer":"L33_CENTER_MARK"})
    msp.add_line((x0,cy),(x0+280,cy),dxfattribs={"layer":"L33_CENTER_MARK"})
    add_hdim(msp,(cx-case["hinge_rect_w"]/2,cy),(cx+case["hinge_rect_w"]/2,cy),y0+22,"DIM_DETAIL")
    add_vdim(msp,(cx,cy-case["hinge_rect_h"]/2),(cx,cy+case["hinge_rect_h"]/2),x0+210,"DIM_DETAIL")

def _resolved_end_notch(case, mirrored=False):
    """Return the actual local x-range of the end cut contour.

    The confirmed new-process outer skin uses the yellow end profile as the
    real laser CUT_OUTER boundary.  It is not an independent inner-cut line.
    """
    width = float(case["flat_width"])
    raw = list(case.get("end_notch_x", []))
    depth = float(case.get("end_notch_depth", 0.0))
    if len(raw) != 2 or depth <= 0:
        return None
    x1, x2 = sorted((float(raw[0]), float(raw[1])))
    if mirrored:
        x1, x2 = width - x2, width - x1
    return (x1, x2, depth)


def _build_plan_cut_outer(case, mirrored=False):
    """Build one closed local CUT_OUTER path for the unfolded plan.

    For the outer skin, the bottom/top yellow U-profile replaces the straight
    edge between x1 and x2.  Therefore no laser line may remain underneath or
    above that profile.  Skeleton parts without this profile remain rectangular.
    """
    width = float(case["flat_width"])
    height = float(case["height"])
    notch = _resolved_end_notch(case, mirrored=mirrored)
    if notch is None:
        return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]

    x1, x2, depth = notch
    # Counter-clockwise closed boundary.  The omitted straight portions
    # x1..x2 at y=0 and y=height are deliberately replaced by the yellow path.
    return [
        (0.0, 0.0),
        (x1, 0.0),
        (x1, depth),
        (x2, depth),
        (x2, 0.0),
        (width, 0.0),
        (width, height),
        (x2, height),
        (x2, height-depth),
        (x1, height-depth),
        (x1, height),
        (0.0, height),
    ]


def _plan_vertical_material_range(case, local_x, mirrored=False):
    """Return the material y-range at local_x for clipping full-height lines."""
    height = float(case["height"])
    notch = _resolved_end_notch(case, mirrored=mirrored)
    if notch is None:
        return 0.0, height
    x1, x2, depth = notch
    if x1 < float(local_x) < x2:
        return depth, height-depth
    return 0.0, height


def add_plan_piece(msp, case, ox, oy, mirrored=False):
    width = float(case["flat_width"])
    height = float(case["height"])

    # Real laser outer boundary: one closed CUT_OUTER polyline.
    # For the outer skin, the confirmed yellow end profile replaces the
    # straight bottom/top line; it is no longer drawn as CUT_INNER.
    local_outer = _build_plan_cut_outer(case, mirrored=mirrored)
    world_outer = [(ox+x, oy+y) for x, y in local_outer]
    msp.add_lwpolyline(
        world_outer + [world_outer[0]],
        dxfattribs={"layer": "L01_OUTER_CUT"},
    )

    # Groove lines are clipped to the real material boundary.  Any groove
    # located inside the end cut-out starts at the yellow laser edge instead
    # of continuing through the removed material.
    for gx, face in zip(case["groove_positions"], case["groove_faces"]):
        px = mirror_x(gx, width) if mirrored else float(gx)
        y1, y2 = _plan_vertical_material_range(case, px, mirrored=mirrored)
        layer = "L10_GROOVE_FRONT" if face == "FRONT" else "L11_GROOVE_BACK"
        msp.add_line((ox+px, oy+y1), (ox+px, oy+y2), dxfattribs={"layer": layer})

    # Edge fixing holes: skeleton = phi4.5 circles; outer skin = 5x9 obrounds.
    for px in [case["edge_slot_x"], width-case["edge_slot_x"]]:
        for py in case["edge_slot_y"]:
            if not (0 < py < height):
                continue
            if case.get("edge_hole_shape") == "CIRCLE":
                add_circle(msp, ox+px, oy+py, 4.5, "L02_INNER_CUT")
            else:
                add_obround_vertical(
                    msp, ox+px, oy+py,
                    case["edge_slot_w"], case["edge_slot_h"],
                    "L02_INNER_CUT",
                )

    # Hinge cuts: skeleton compound cut; outer skin 46x190 obround R23.
    hinge_x = width-case["hinge_center_from_function_edge"] if mirrored else case["hinge_center_from_function_edge"]
    for d_top in case["hinge_from_top"]:
        cy = oy+height-d_top
        if case.get("hinge_shape") == "OBROUND":
            add_obround_vertical(
                msp, ox+hinge_x, cy,
                case["hinge_rect_w"], case["hinge_rect_h"],
                "L02_INNER_CUT",
            )
        else:
            add_center_rect(
                msp, ox+hinge_x, cy,
                case["hinge_rect_w"], case["hinge_rect_h"],
                "L02_INNER_CUT",
            )
            for dx, dy, dia in case.get("hinge_inner_holes", []):
                # Horizontal mirror only: phi6 stays above, phi16 stays below.
                add_circle(msp, ox+hinge_x+dx, cy+dy, dia, "L02_INNER_CUT")

    # Skeleton end holes; outer skin has no entries here.
    hole_xs = list(case.get("end_hole_x", []))
    if mirrored:
        hole_xs = [mirror_x(x, width) for x in hole_xs]
    for px in hole_xs:
        add_circle(msp, ox+px, oy+case["bottom_hole_from_bottom"], case["end_hole_d"], "L02_INNER_CUT")
        add_circle(msp, ox+px, oy+height-case["top_hole_from_top"], case["end_hole_d"], "L02_INNER_CUT")

    # Top/bottom small slots.
    slot_xs = list(case.get("small_slot_x", []))
    if mirrored:
        slot_xs = [mirror_x(x, width) for x in slot_xs]
    for px, dtop in zip(slot_xs, case.get("top_slot_from_top", [])):
        add_center_rect(msp, ox+px, oy+height-dtop, case["small_slot_w"], case["small_slot_h"], "L02_INNER_CUT")
    for px, dbottom in zip(slot_xs, case.get("bottom_slot_from_bottom", [])):
        add_center_rect(msp, ox+px, oy+dbottom, case["small_slot_w"], case["small_slot_h"], "L02_INNER_CUT")

def draw_type_block(msp, case, left_x, top_y):
    # left detail stack
    draw_flat_section(msp, case, left_x, top_y-220)
    draw_folded_section(msp, case, left_x, top_y-840)
    draw_hinge_detail(msp, case, left_x, top_y-1560)

def add_plan_pair(msp, case, left_x, base_y, title_prefix, include_left=True, include_right=True):
    """绘制同一材料的左件/右件。两个都输出时并排；只输出一个时占用左侧位置。"""
    piece_gap = 170
    positions = []
    if include_left:
        positions.append((left_x, False, "左件"))
    if include_right:
        right_x = left_x + case["flat_width"] + piece_gap if include_left else left_x
        positions.append((right_x, True, "右件"))

    for ox, mirrored, side_name in positions:
        add_plan_piece(msp, case, ox, base_y, mirrored=mirrored)
        width = case["flat_width"]
        top_y = base_y + case["height"]
        right_edge = ox + width
        first_front = next(
            (x for x, face in zip(case["groove_positions"], case["groove_faces"]) if face == "FRONT"),
            case["hinge_center_from_function_edge"],
        )

        if mirrored:
            add_hdim(
                msp,
                (right_edge-case["hinge_center_from_function_edge"], top_y),
                (right_edge, top_y),
                top_y+38,
            )
            add_hdim(
                msp,
                (right_edge-first_front, top_y),
                (right_edge, top_y),
                top_y+72,
            )
        else:
            add_hdim(
                msp,
                (ox, top_y),
                (ox+case["hinge_center_from_function_edge"], top_y),
                top_y+38,
            )
            add_hdim(
                msp,
                (ox, top_y),
                (ox+first_front, top_y),
                top_y+72,
            )

        add_hdim(msp, (ox, top_y), (right_edge, top_y), top_y+112, "DIM_PLAN")
        add_vdim(msp, (right_edge, base_y), (right_edge, top_y), right_edge+60, "DIM_PLAN")

        for idx, dtop in enumerate(case["hinge_from_top"]):
            if mirrored:
                add_vdim(
                    msp,
                    (right_edge, top_y),
                    (right_edge, top_y-dtop),
                    right_edge+100+idx*38,
                    "DIM_PLAN",
                )
            else:
                add_vdim(
                    msp,
                    (ox, top_y),
                    (ox, top_y-dtop),
                    ox-55-idx*38,
                    "DIM_PLAN",
                )

        add_cn_mtext(
            msp,
            f"{case['name']}{side_name}展开平面图",
            ox,
            top_y+228,
            height=12,
            width=220,
        )
        add_cn_mtext(
            msp,
            f"合页中心距功能边：{case['hinge_center_from_function_edge']:.1f}",
            ox,
            top_y+196,
            height=7,
            width=280,
            layer="L32_PART_ID",
        )
        add_cn_mtext(
            msp,
            f"合页中心距顶部：{'、'.join(str(int(v)) for v in case['hinge_from_top'])}",
            ox,
            top_y+164,
            height=6,
            width=340,
        )

    # 展开链标注放在实际输出的第一件下方
    if positions:
        first_ox = positions[0][0]
        run = 0.0
        for idx, seg in enumerate(case["plan_segments"]):
            dim_base = base_y-55 if idx % 2 == 0 else base_y-88
            add_hdim(
                msp,
                (first_ox+run, base_y),
                (first_ox+run+seg, base_y),
                dim_base,
                "DIM_DETAIL",
            )
            run += seg

def _folded_left_x(case, center_x):
    outer=case["outer_profile"]
    d1=offset_open_polyline(outer,-case["groove_depth"])
    d2=offset_open_polyline(outer,-(case["thickness"]-case["groove_depth"]))
    inner=offset_open_polyline(outer,-case["thickness"])
    pts=outer+d1+d2+inner
    min_x=min(x for x,y in pts); max_x=max(x for x,y in pts)
    return center_x-(max_x-min_x)/2


def _draw_side_plan_dimensions(msp, case, ox, oy, mirrored, side_name):
    width=case["flat_width"]
    top=oy+case["height"]
    right=ox+width

    inner_points, outer_pairs = _standard_groove_dimensions(case, mirrored=mirrored)
    _draw_three_row_horizontal_dimensions(
        msp, x0=ox, datum_y=top, width=width,
        inner_points=inner_points, outer_pairs=outer_pairs,
        inner_base_y=top+42, outer_base_y=top+88, total_base_y=top+136,
    )

    add_cn_mtext(msp,f"{case['name']}{side_name}展开平面图",ox,top+218,height=9,width=250,layer="L32_PART_ID")
    add_cn_mtext(
        msp,
        f"合页中心距功能边：{case['hinge_center_from_function_edge']:.1f}\\P距顶部：{'、'.join(str(int(v)) for v in case['hinge_from_top'])}",
        ox,top+194,height=4.6,width=430,
    )

    if side_name=="左件":
        add_vdim(msp,(right,oy),(right,top),right+58,"DIM_PLAN")
        for idx,dtop in enumerate(case["hinge_from_top"]):
            add_vdim(msp,(ox,top),(ox,top-dtop),ox-48-idx*32,"DIM_SECTION")
    else:
        add_vdim(msp,(ox,oy),(ox,top),ox-58,"DIM_PLAN")
        for idx,dtop in enumerate(case["hinge_from_top"]):
            add_vdim(msp,(right,top),(right,top-dtop),right+48+idx*32,"DIM_SECTION")


def _draw_side_column(msp, case, column_x, plan_base_y, *, mirrored, side_name):
    """Top-to-bottom layout: folded section, flat section, unfolded plan."""
    column_width=760.0
    center_x=column_x+column_width/2
    plan_x=center_x-case["flat_width"]/2
    plan_top=plan_base_y+case["height"]
    flat_y=plan_top+430
    folded_y=flat_y+410

    add_plan_piece(msp,case,plan_x,plan_base_y,mirrored=mirrored)
    _draw_side_plan_dimensions(msp,case,plan_x,plan_base_y,mirrored,side_name)

    # Flat section and plan share the same vertical centerline.
    flat_x=center_x-case["flat_width"]/2
    draw_flat_section(msp,case,flat_x,flat_y,mirrored=mirrored)
    draw_folded_section(msp,case,_folded_left_x(case,center_x),folded_y,mirrored=mirrored)

    add_cn_mtext(msp,f"{case['name']}{side_name}",column_x+20,folded_y+340,height=14,width=320,layer="L32_PART_ID")
    return {
        "column_x":column_x,
        "center_x":center_x,
        "plan_x":plan_x,
        "flat_y":flat_y,
        "folded_y":folded_y,
    }


def draw_left_right_vertical_layout(
    msp,
    skeleton_params,
    outer_params,
    *,
    include_left=True,
    include_right=True,
    origin_x=0.0,
    origin_y=0.0,
    show_title=True,
):
    sk=make_skeleton_case(**skeleton_params)
    ot=make_outer_case(**outer_params)
    plan_base_y=origin_y+180
    columns=[]
    column_x=origin_x+80
    gap=820
    if include_left:
        columns.append((sk,column_x,False,"左件")); column_x+=gap
    if include_right:
        columns.append((sk,column_x,True,"右件")); column_x+=gap
    if include_left:
        columns.append((ot,column_x,False,"左件")); column_x+=gap
    if include_right:
        columns.append((ot,column_x,True,"右件")); column_x+=gap
    if not columns:
        raise ValueError("左门框和右门框至少选择一个。")

    max_folded=plan_base_y+max(sk["height"],ot["height"])+840
    if show_title:
        add_cn_mtext(msp,f"左右框参数化生产图（默认新工艺）｜门高{sk['height']:.0f}｜骨架{sk['short_top']:.0f}/{sk['long_bottom']:.0f}｜外皮{ot['short_top']:.0f}/{ot['long_bottom']:.0f}",origin_x+70,max_folded+390,height=17,width=1500)
        add_cn_mtext(msp,"统一三行标注：内侧报槽、外侧报槽、展开总长；展开截面下侧为内槽、上侧为外槽和总长，展开平面三行均放在图形上侧。\\P右件三图同步镜像；固定孔按高度自动均布；公共详图分别提供骨架与外皮单组合页避让孔示意图。",origin_x+70,max_folded+352,height=6.2,width=2000)

    results=[]
    for case,cx,mirrored,side_name in columns:
        results.append(_draw_side_column(msp,case,cx,plan_base_y,mirrored=mirrored,side_name=side_name))

    # Shared public details: skeleton + outer hinge-relief details.
    detail_x=column_x+90
    detail_y=plan_base_y+max(sk["height"],ot["height"])+430
    add_cn_mtext(msp,"公共详图",detail_x,detail_y+330,height=13,width=260,layer="L32_PART_ID")
    draw_hinge_detail(msp,sk,detail_x,detail_y)
    draw_hinge_detail(msp,ot,detail_x+470,detail_y)
    column_x=detail_x+930
    return {
        "skeleton":sk,
        "outer":ot,
        "width":column_x-origin_x+80,
        "height":max_folded-origin_y+430,
        "columns":results,
    }


# 左右框默认切换为新工艺样例：外皮55/62，骨架52/59。
def generate_combined_dxf(
    output_path,
    skeleton_params,
    outer_params,
    title="左右框参数化生产图",
    include_left=True,
    include_right=True,
):
    doc=create_doc(); msp=doc.modelspace()
    result=draw_left_right_vertical_layout(
        msp,
        skeleton_params,
        outer_params,
        include_left=include_left,
        include_right=include_right,
        origin_x=0,
        origin_y=0,
        show_title=True,
    )
    # Replace default title text by adding the requested order title at the far top.
    add_cn_mtext(msp,title,70,result["height"]-55,height=18,width=1000,layer="L32_PART_ID")
    doc.saveas(output_path)
    audit=ezdxf.readfile(output_path).audit()
    return {
        "output":str(output_path),
        "audit_errors":len(audit.errors),
        "audit_fixes":len(audit.fixes),
        "skeleton_hinge_x":result["skeleton"]["hinge_center_from_function_edge"],
        "outer_hinge_x":result["outer"]["hinge_center_from_function_edge"],
        "include_left":include_left,
        "include_right":include_right,
        "layout":"vertical_columns",
        "drawing_width":result["width"],
        "drawing_height":result["height"],
    }

