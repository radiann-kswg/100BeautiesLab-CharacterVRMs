"""Assemble matched Unity BakeMesh clearance measurements and head-turn photographs.

python summarize_spring_clearance.py --before <control capture> --after <production capture>
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
NUMBERS = (6, 49, 57, 85)
POSES = ("neutral-25deg","head-12-aa-065","root-000","root-006","root-012","root-018",
         "root-024","root-036","root-090","root-150")


def read_capture(folder, number, native=None):
    report = json.loads((folder/"unity.json").read_text(encoding="utf8"))
    sha = report["sha256"]
    if native and hashlib.sha256(native.read_bytes()).hexdigest() != sha:
        raise ValueError(f"Capture does not represent the production VRM: {folder}")
    data = {}
    per_chain = {}
    for name in POSES:
        source = json.loads((folder/"spring-clearance"/f"{name}.json").read_text(encoding="utf8"))
        if source["pose"] != name or source["sha256"] != sha or source["grid"] != 160:
            raise ValueError(f"Mixed or outdated clearance recording: #{number}, {name}")
        visible = (source["leftEyePixels"], source["rightEyePixels"])
        if not min(visible):
            raise ValueError(f"Missing weighted eye surface: #{number}")
        nonzero = []
        for spring in source["springs"]:
            key = spring["chain"]
            left, right = spring["leftEyeOverlapPixels"], spring["rightEyeOverlapPixels"]
            hair = "hair" in key.lower()
            # Tail chains can span both sides at rest. Their lateral coordinate
            # is not an indication of a hair crossing the facial midline.
            crossed = spring["acrossHeadMidline"] if hair else None
            rec = per_chain.setdefault(key, {"weighted_vertices":spring["weightedVertices"],
                "max_left_eye_overlap_px":0, "max_right_eye_overlap_px":0,
                "max_eye_overlap_fraction":0., "max_hair_vertices_across_midline":0 if hair else None})
            rec["max_left_eye_overlap_px"] = max(rec["max_left_eye_overlap_px"],left)
            rec["max_right_eye_overlap_px"] = max(rec["max_right_eye_overlap_px"],right)
            rec["max_eye_overlap_fraction"] = max(rec["max_eye_overlap_fraction"],left/visible[0],right/visible[1])
            if hair:
                rec["max_hair_vertices_across_midline"] = max(rec["max_hair_vertices_across_midline"],crossed)
            if left or right or crossed:
                nonzero.append({"chain":key,"left_px":left,"right_px":right,"hair_across_midline":crossed})
        data[name] = {"left_eye_px":visible[0],"right_eye_px":visible[1],"nonzero_samples":nonzero}
    if {s["chain"] for s in report["springs"]} != set(per_chain):
        raise ValueError("Spring clearance and motion probes report different sets of chains")
    for motion in report["springs"]:
        rec = per_chain[motion["chain"]]
        rec["peak_weighted_vertex_motion_mm"] = motion["peakSkinMeters"]*1000
        rec["terminal_displacement_after_150_steps_mm"] = motion["finalTipMeters"]*1000
    image = folder/"mouth/head-turn-speaking.png"
    return {"sha256":sha,"unity":report["unity"],"play_mode":report["playMode"],
            "head_turn_photo_sha256":hashlib.sha256(image.read_bytes()).hexdigest(),
            "poses":data,"chains":per_chain}, image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before",type=Path,required=True)
    parser.add_argument("--after",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=HERE)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    result = {"method":"Actual Unity Play Mode BakeMesh. Orthographic 160×160 rays over a 0.40m square centred "
        "on the midpoint of the eye bones. A spring triangle must be more than 0.5mm in front of an eye "
        "triangle. All three vertices belong to the same measured chain or eye; each has an owner with "
        "greater than 0.30 weight. Counts describe projected geometry; opacity and intervening static hair "
        "are evaluated separately in the photographs. Lateral hair travel counts vertices more than 5mm "
        "beyond the opposite side of the eye-bone midsagittal plane.",
        "poses":"Neutral and head yaw +12° with Aa 65% use a 25° camera. Root movement uses a frontal camera "
        "at rest and frames 6, 12, 18, 24, 36, 90, and 150 of the fixed 60 Hz perturbation.",
        "implementation":"CharacterReview.SpringClearance.cs", "models":{}}
    tile, side, top = 232, 64, 44
    board=Image.new("RGB",(side+2*tile,top+4*tile),"#2b3036")
    pen=ImageDraw.Draw(board)
    font=ImageFont.truetype("segoeui.ttf",19)
    for col, label in enumerate(("Before","After")):
        pen.text((side+(col+.5)*tile,top/2),label,anchor="mm",fill="white",font=font)
    for row,n in enumerate(NUMBERS):
        model = {}
        pen.text((side/2,top+(row+.5)*tile),f"#{n}",anchor="mm",fill="white",font=font)
        for col,(label,folder) in enumerate((("before",args.before),("after",args.after))):
            base = HERE.parent.parent/f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm" if label=="after" else None
            record, photo = read_capture(folder/f"Corefolder-{n}",n,base)
            model[label]=record
            with Image.open(photo) as source:
                board.paste(source.convert("RGB").resize((tile-2,tile-2),Image.Resampling.LANCZOS),
                            (side+col*tile,top+row*tile))
        result["models"][n]=model
    board.save(args.out/"spring-clearance.png")
    (args.out/"spring-clearance.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")


if __name__ == "__main__":
    main()
