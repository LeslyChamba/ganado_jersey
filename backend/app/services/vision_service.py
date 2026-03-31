"""
JER-WEIGHT — Vision Service
  Foto trasera  → YOLOv8 → BCS
  Foto lateral  → SAM    → silueta → OpenCV → medidas morfométricas
"""
import logging, time
import numpy as np
import cv2
from pathlib import Path
from typing import Tuple

from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

PROYECTO_DIR = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
SAM_MODEL    = PROYECTO_DIR / "models_pt" / "sam_vit_b.pth"
BCS_MODEL    = Path(r"C:\Users\HP\Documents\Proyecto_Peso_BCS_Vacas\02_Models\BCS\best.pt")


# ── SAM ──────────────────────────────────────────────────────────────────────
def segmentar_con_sam(image_bgr):
    import torch
    from segment_anything import sam_model_registry, SamPredictor
    h, w = image_bgr.shape[:2]
    sam  = sam_model_registry["vit_b"](checkpoint=str(SAM_MODEL))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam.to(device=device)
    predictor = SamPredictor(sam)
    predictor.set_image(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    cx, cy   = w//2, h//2
    fg_pts   = np.array([[cx,cy],[cx-w//8,cy],[cx+w//8,cy],[cx,cy-h//8],[cx,cy+h//10]])
    bg_pts   = np.array([[10,10],[w-10,10],[10,h-10],[w-10,h-10],[cx,10],[10,cy],[w-10,cy]])
    all_pts  = np.vstack([fg_pts, bg_pts])
    all_lbl  = np.array([1]*5+[0]*7)
    masks, scores, _ = predictor.predict(point_coords=all_pts, point_labels=all_lbl, multimask_output=True)
    mejor_score, mejor_mask = -1, None
    for mask, score in zip(masks, scores):
        fill = mask.sum()/(h*w)
        if 0.08 <= fill <= 0.80 and score > mejor_score:
            mejor_score, mejor_mask = score, mask
    if mejor_mask is None:
        mejor_mask = masks[np.argmax(scores)]
    mask_bin = mejor_mask.astype(np.uint8)*255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,15))
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts: return mask_bin, None
    main = max(cnts, key=cv2.contourArea)
    mc   = np.zeros_like(mask_bin)
    cv2.drawContours(mc,[main],-1,255,-1)
    return mc, main


# ── Orientación ──────────────────────────────────────────────────────────────
def detectar_orientacion(mask, x_bb, y_bb, bw, bh):
    y_top, y_mid = y_bb+int(bh*0.05), y_bb+int(bh*0.45)
    tercio = bw//3
    def densidad(x0,x1):
        t=0
        for xi in range(x0,min(x1,mask.shape[1])): t+=int(np.sum(mask[y_top:y_mid,xi]>0))
        return t/max(x1-x0,1)
    return "derecha" if densidad(x_bb,x_bb+tercio)<densidad(x_bb+2*tercio,x_bb+bw) else "izquierda"


def _col_pata(mask,x_bb,y_bb,bw,bh,lado):
    y_ini,y_fin = y_bb+int(bh*0.18), y_bb+int(bh*0.60)
    min_px = int(bh*0.10)
    if lado=="derecha":
        x_ini=x_bb+int(bw*0.50); x_fin=x_bb+bw-int(bw*0.25)
        for xi in range(min(x_fin,mask.shape[1])-1,x_ini,-1):
            if len(np.where(mask[y_ini:y_fin,xi]>0)[0])>=min_px: return xi
        return x_fin
    else:
        x_ini=x_bb+int(bw*0.22); x_fin=x_bb+int(bw*0.50)
        for xi in range(x_ini,min(x_fin,mask.shape[1])):
            if len(np.where(mask[y_ini:y_fin,xi]>0)[0])>=min_px: return xi
        return x_ini


def detectar_lomo(mask,x_bb,y_bb,bw,bh,w_img):
    xs_v,tops_r=[],[]
    for xi in range(x_bb,min(x_bb+bw,w_img)):
        ys=np.where(mask[:,xi]>0)[0]
        if len(ys)>=2: xs_v.append(xi); tops_r.append(float(ys[0]))
    if len(xs_v)<20: return x_bb,x_bb+bw,tops_r,xs_v,"derecha"
    xs_arr=np.array(xs_v); tops_arr=np.array(tops_r)
    win=max(len(xs_arr)//10,5)
    tops_s=np.array([np.median(tops_arr[max(0,i-win):i+win+1]) for i in range(len(tops_arr))])
    ori=detectar_orientacion(mask,x_bb,y_bb,bw,bh)
    mg=int(len(xs_arr)*0.10)
    zona=tops_s[mg:len(xs_arr)-mg]; umbral=np.percentile(zona,30); tol=bh*0.05
    en_lomo=tops_s<=(umbral+tol); en_lomo[:mg]=False; en_lomo[len(xs_arr)-mg:]=False
    idx=np.where(en_lomo)[0]
    if len(idx)>=5:
        if ori=="derecha":
            x_enc=_col_pata(mask,x_bb,y_bb,bw,bh,"derecha")
            x_isq=_col_pata(mask,x_bb,y_bb,bw,bh,"izquierda")
        else:
            x_enc=_col_pata(mask,x_bb,y_bb,bw,bh,"izquierda")
            x_isq=_col_pata(mask,x_bb,y_bb,bw,bh,"derecha")
    else:
        if ori=="derecha":
            x_enc=int(np.percentile(xs_arr,22)); x_isq=int(np.percentile(xs_arr,78))
        else:
            x_enc=int(np.percentile(xs_arr,78)); x_isq=int(np.percentile(xs_arr,22))
    if abs(x_isq-x_enc)<bw*0.20:
        if ori=="derecha":
            x_enc=int(np.percentile(xs_arr,22)); x_isq=int(np.percentile(xs_arr,78))
        else:
            x_enc=int(np.percentile(xs_arr,78)); x_isq=int(np.percentile(xs_arr,22))
    return x_enc,x_isq,tops_s.tolist(),xs_v,ori


def _seg(ys):
    if len(ys)<2: return 0.0
    gaps=np.where(np.diff(ys)>8)[0]
    if not len(gaps): return float(ys[-1]-ys[0])
    segs,p=[],0
    for g in gaps: segs.append(ys[g]-ys[p]); p=g+1
    segs.append(ys[-1]-ys[p])
    return float(max(segs))


# ── Medidas morfométricas ────────────────────────────────────────────────────
def medir(image, mask, contour) -> dict:
    h_img,w_img = image.shape[:2]
    x_bb,y_bb,bw,bh = cv2.boundingRect(contour)
    max_h_px=0.0; x_ac=0
    for xi in range(x_bb+int(bw*0.25),min(x_bb+int(bw*0.60),w_img)):
        ys=np.where(mask[:,xi]>0)[0]
        if len(ys)>=2:
            h=float(ys[-1]-ys[0])
            if h>max_h_px: max_h_px=h; x_ac=xi
    if max_h_px<bh*0.35: max_h_px=float(bh); x_ac=x_bb+bw//2
    px=max_h_px/120.0
    x_enc,x_isq,tops_s,xs_v,ori=detectar_lomo(mask,x_bb,y_bb,bw,bh,w_img)
    lc_px=max(abs(x_isq-x_enc),1); x_izq=min(x_enc,x_isq); lc_cm=(lc_px/px)+60
    x_pt=np.clip(x_izq+int(lc_px*0.28),0,w_img-1)
    y_fs=y_bb+int(bh*0.05); y_fi=y_bb+int(bh*0.58)
    ys_pt=np.where(mask[:,x_pt]>0)[0]
    ys_tor=ys_pt[(ys_pt>=y_fs)&(ys_pt<=y_fi)]
    h_tor=float(ys_tor[-1]-ys_tor[0]) if len(ys_tor)>=2 else _seg(ys_pt)
    pt_cm=(h_tor*np.pi)/px
    ys_ag=np.where(mask[:,x_isq]>0)[0]
    ag_cm=(float(ys_ag[-1]-ys_ag[0]) if len(ys_ag)>=2 else max_h_px)/px
    x_cad=np.clip(x_izq+int(lc_px*0.80),0,w_img-1)
    ys_c=np.where(mask[:,x_cad]>0)[0]
    ys_ct=ys_c[(ys_c>=y_fs)&(ys_c<=y_fi)]
    cad_cm=(float(ys_ct[-1]-ys_ct[0]) if len(ys_ct)>=2 else _seg(ys_c))/px
    area=float(cv2.contourArea(contour)); perim=float(cv2.arcLength(contour,True))
    htor_norm=h_tor/max_h_px if max_h_px>0 else 0.0
    cad_h_px=float(ys_ct[-1]-ys_ct[0]) if len(ys_ct)>=2 else 0.0
    cad_norm=cad_h_px/max_h_px if max_h_px>0 else 0.0
    return {
        "lc":round(lc_cm,1),"ac":round(max_h_px/px,1),"ag":round(ag_cm,1),
        "pt":round(pt_cm,1),"cadera":round(cad_cm,1),
        "area_norm":round(area/(w_img*h_img),5),
        "ratio_lh":round(lc_px/max_h_px if max_h_px>0 else 1,4),
        "perim_norm":round(perim/max_h_px if max_h_px>0 else 1,4),
        "htor_norm":round(htor_norm,4),"cad_norm":round(cad_norm,4),
        "px_per_cm":round(px,4),
        "confidence":round(min(area/float(bw*bh),1.0) if bw*bh>0 else 0,3),
        "orientacion":ori,
        "x_bb":x_bb,"y_bb":y_bb,"bw":bw,"bh":bh,
        "x_enc":x_enc,"x_isq":x_isq,"x_pt":x_pt,"x_cad":x_cad,
        "x_ac":x_ac,"max_h_px":max_h_px,"y_fs":y_fs,"y_fi":y_fi,
    }


# ── BCS con YOLO ────────────────────────────────────────────────────────────
def predecir_bcs(image_bgr) -> Tuple[float, float]:
    try:
        import tempfile, os
        from ultralytics import YOLO
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, image_bgr); tmp_path=tmp.name
        res=YOLO(str(BCS_MODEL))(tmp_path, verbose=False)
        os.unlink(tmp_path)
        probs=res[0].probs; top_idx=int(probs.top1)
        bcs_conf=float(probs.top1conf.item())
        cm={0:3.0,1:3.25,2:3.5,3:4.0,4:4.5}
        bcs_score=cm.get(top_idx,3.0)
        logger.info(f"BCS YOLO: {bcs_score} conf:{bcs_conf:.2f}")
        return bcs_score, bcs_conf
    except Exception as e:
        logger.warning(f"YOLO BCS falló: {e} → BCS=3.0")
        return 3.0, 0.0


# ── Servicio principal ───────────────────────────────────────────────────────
class VisionService:
    async def analizar_imagenes(
        self, bytes_lateral: bytes, bytes_trasera: bytes
    ) -> Tuple[MorfometriaData, float, float, float]:
        """Retorna (morfometria, confianza_vision, bcs, bcs_conf)"""
        nparr_lat=np.frombuffer(bytes_lateral,np.uint8)
        img_lat=cv2.imdecode(nparr_lat,cv2.IMREAD_COLOR)
        nparr_tra=np.frombuffer(bytes_trasera,np.uint8)
        img_tra=cv2.imdecode(nparr_tra,cv2.IMREAD_COLOR)
        if img_lat is None or img_tra is None:
            raise ValueError("No se pudieron decodificar las imágenes")
        for img in [img_lat, img_tra]:
            h0,w0=img.shape[:2]
            if max(h0,w0)>1280:
                f=1280/max(h0,w0); img=cv2.resize(img,(int(w0*f),int(h0*f)))

        bcs_score, bcs_conf = predecir_bcs(img_tra)
        mask, contour = segmentar_con_sam(img_lat)
        if contour is None:
            raise ValueError("SAM no pudo segmentar la vaca en la foto lateral")
        m = medir(img_lat, mask, contour)
        logger.info(f"LC={m['lc']}cm PT={m['pt']}cm AC={m['ac']}cm BCS={bcs_score}")

        morfo = MorfometriaData(
            alzada_cm              = m["ac"],
            largo_corporal_cm      = m["lc"],
            profundidad_toracica_cm= round(m["pt"]/np.pi,1),
            ancho_caderas_cm       = m["cadera"],
            perimetro_toracico_cm  = m["pt"],
            longitud_grupa_cm      = m.get("ag"),
            ancho_grupa_cm         = m["cadera"],
        )
        # Metadatos para el estimador
        morfo._medidas_raw = m
        morfo._bcs         = bcs_score
        morfo._bcs_conf    = bcs_conf
        return morfo, m["confidence"], bcs_score, bcs_conf


vision_service = VisionService()
