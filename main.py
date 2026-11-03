"""
API FastAPI - SUD-KIVU IRL DIGITAL
Lancer :  uvicorn main:app --reload      (docs : http://localhost:8000/docs)
Le logiciel n'invente aucun taux : il applique les paramètres légaux saisis par l'administrateur.
"""
import hashlib, hmac, os, secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String,
                        UniqueConstraint, create_engine, func, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./irl.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-a-changer")
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "60"))
DOC_SECRET = os.getenv("DOC_SECRET", JWT_SECRET)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String, unique=True)
    nom: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    commune: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mdp_hash: Mapped[str] = mapped_column(String)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)


class Contribuable(Base):
    __tablename__ = "contribuables"
    id_contribuable: Mapped[str] = mapped_column(String, primary_key=True)
    nom: Mapped[str] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    telephone: Mapped[Optional[str]] = mapped_column(String)
    commune: Mapped[Optional[str]] = mapped_column(String)


class Bien(Base):
    __tablename__ = "biens"
    id_bien: Mapped[str] = mapped_column(String, primary_key=True)
    id_contribuable: Mapped[str] = mapped_column(ForeignKey("contribuables.id_contribuable"))
    commune: Mapped[str] = mapped_column(String, index=True)
    quartier: Mapped[Optional[str]] = mapped_column(String)
    avenue: Mapped[Optional[str]] = mapped_column(String)
    type_bien: Mapped[Optional[str]] = mapped_column(String)
    usage: Mapped[str] = mapped_column(String)
    nb_logements: Mapped[int] = mapped_column(Integer, default=1)
    occupation: Mapped[Optional[str]] = mapped_column(String)
    statut: Mapped[str] = mapped_column(String, default="En vérification")
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)


class Contrat(Base):
    __tablename__ = "contrats"
    id_contrat: Mapped[str] = mapped_column(String, primary_key=True)
    id_bien: Mapped[str] = mapped_column(ForeignKey("biens.id_bien"))
    locataire: Mapped[str] = mapped_column(String)
    loyer_mensuel: Mapped[float] = mapped_column(Numeric(12, 2))
    periodicite: Mapped[str] = mapped_column(String, default="Mensuelle")
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date] = mapped_column(Date)


class Declaration(Base):
    __tablename__ = "declarations"
    __table_args__ = (UniqueConstraint("id_bien", "periode"),)
    ref: Mapped[str] = mapped_column(String, primary_key=True)
    id_bien: Mapped[str] = mapped_column(ForeignKey("biens.id_bien"), index=True)
    periode: Mapped[int] = mapped_column(Integer)
    loyer_annuel_declare: Mapped[float] = mapped_column(Numeric(14, 2))
    taux_applique: Mapped[float] = mapped_column(Numeric(6, 2))
    montant_du: Mapped[float] = mapped_column(Numeric(14, 2))
    date: Mapped[date] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String, default="Soumise")
    canal: Mapped[Optional[str]] = mapped_column(String)


class Paiement(Base):
    __tablename__ = "paiements"
    ref_paiement: Mapped[str] = mapped_column(String, primary_key=True)
    ref_decl: Mapped[str] = mapped_column(ForeignKey("declarations.ref"), index=True)
    montant: Mapped[float] = mapped_column(Numeric(14, 2))
    date: Mapped[date] = mapped_column(Date)
    canal: Mapped[Optional[str]] = mapped_column(String)
    confirme: Mapped[bool] = mapped_column(Boolean, default=False)


class Parametre(Base):
    __tablename__ = "parametres"
    cle: Mapped[str] = mapped_column(String, primary_key=True)
    valeur: Mapped[str] = mapped_column(String)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    utilisateur: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    dossier: Mapped[Optional[str]] = mapped_column(String)
    ancienne: Mapped[Optional[str]] = mapped_column(String)
    nouvelle: Mapped[Optional[str]] = mapped_column(String)


# ----------------------------- sécurité -----------------------------
def hash_pwd(pwd: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${dk}"


def check_pwd(pwd: str, stored: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_pwd(pwd, salt), stored)


PERMS = {  # lecture / création / modification / suppression
    "Administrateur": dict(read=True, create=True, update=True, delete="politique"),
    "Direction DPMER": dict(read=True, create=False, update=False, delete=False),
    "Chef de centre": dict(read=True, create=True, update=True, delete="limitée"),
    "Agent d'identification": dict(read=True, create=True, update="limitée", delete=False),
    "Agent de contrôle": dict(read=True, create=True, update=True, delete=False),
    "Agent de recouvrement": dict(read=True, create=True, update="limitée", delete=False),
    "Responsable financier": dict(read=True, create=False, update=False, delete=False),
    "Auditeur": dict(read=True, create=False, update=False, delete=False),
}
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    with SessionLocal() as s:
        yield s


def current_user(token: str = Depends(oauth2), s: Session = Depends(get_db)) -> Utilisateur:
    try:
        login = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Jeton invalide ou expiré")
    u = s.scalar(select(Utilisateur).where(Utilisateur.login == login, Utilisateur.actif))
    if not u:
        raise HTTPException(401, "Utilisateur inconnu")
    return u


def require(action: str):
    def dep(u: Utilisateur = Depends(current_user)) -> Utilisateur:
        if not PERMS[u.role][action]:
            raise HTTPException(403, f"Le rôle « {u.role} » n'a pas le droit : {action}")
        return u
    return dep


def log(s: Session, u: Utilisateur, action, dossier="-", ancienne="-", nouvelle="-"):
    s.add(Audit(utilisateur=f"{u.nom} ({u.login})", action=action, dossier=dossier,
                ancienne=str(ancienne), nouvelle=str(nouvelle)))


def check_scope(u: Utilisateur, commune: str):
    if u.commune and u.commune != commune:
        raise HTTPException(403, "Hors de votre ressort")


def get_taux(s: Session, usage: str) -> float:
    p = s.get(Parametre, f"taux:{usage}")
    if not p:
        raise HTTPException(409, f"Aucun taux légal paramétré pour l'usage « {usage} » "
                                 "(l'administrateur doit le saisir)")
    return float(p.valeur)


def doc_code(ref_paiement: str, ref_decl: str, montant: float) -> str:
    raw = f"{ref_paiement}|{ref_decl}|{float(montant):.2f}|{DOC_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


# ----------------------------- schémas -----------------------------
class BienIn(BaseModel):
    proprietaire: str
    type_contribuable: str = "Personne physique"
    telephone: Optional[str] = None
    commune: str
    quartier: Optional[str] = None
    avenue: str
    type_bien: str
    usage: str
    nb_logements: int = Field(1, ge=1)
    occupation: str = "Occupé"
    lat: Optional[float] = None
    lon: Optional[float] = None


class StatutIn(BaseModel):
    statut: str


class DeclarationIn(BaseModel):
    id_bien: str
    periode: int
    loyer_annuel_declare: float = Field(gt=0)
    canal: str = "Agent terrain"


class PaiementIn(BaseModel):
    ref_decl: str
    montant: float = Field(gt=0)
    canal: str
    confirme: bool = False


class ParametresIn(BaseModel):
    taux: dict[str, float]


# ----------------------------- application -----------------------------
app = FastAPI(title="SUD-KIVU IRL DIGITAL API", version="0.1.0")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.scalar(select(func.count()).select_from(Utilisateur)):
            pwd = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(10)
            s.add(Utilisateur(login="admin", nom="Administrateur provincial", role="Administrateur",
                              mdp_hash=hash_pwd(pwd)))
            s.commit()
            print(f"[INIT] Compte admin créé. Mot de passe initial : {pwd}  (à changer)")


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), s: Session = Depends(get_db)):
    u = s.scalar(select(Utilisateur).where(Utilisateur.login == form.username, Utilisateur.actif))
    if not u or not check_pwd(form.password, u.mdp_hash):
        raise HTTPException(401, "Identifiant ou mot de passe incorrect")
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MIN)
    token = jwt.encode({"sub": u.login, "role": u.role, "exp": exp}, JWT_SECRET, algorithm="HS256")
    log(s, u, "Connexion")
    s.commit()
    return {"access_token": token, "token_type": "bearer", "role": u.role}


@app.get("/biens")
def liste_biens(commune: Optional[str] = None, u: Utilisateur = Depends(require("read")),
                s: Session = Depends(get_db)):
    q = select(Bien)
    if u.commune:
        q = q.where(Bien.commune == u.commune)
    elif commune:
        q = q.where(Bien.commune == commune)
    return s.scalars(q).all()


@app.post("/biens", status_code=201)
def creer_bien(b: BienIn, u: Utilisateur = Depends(require("create")), s: Session = Depends(get_db)):
    check_scope(u, b.commune)
    code = b.commune[:3].upper()
    n = s.scalar(select(func.count()).select_from(Bien).where(Bien.commune == b.commune)) + 1
    id_bien = f"SK-IRL-UVI-{code}-{n:06d}"
    dup = s.scalar(select(Bien).join(Contribuable).where(
        func.lower(Contribuable.nom) == b.proprietaire.strip().lower(),
        func.lower(Bien.avenue) == b.avenue.strip().lower()))
    if dup:
        raise HTTPException(409, f"Doublon possible : {dup.id_bien}")
    ctb = s.scalar(select(Contribuable).where(func.lower(Contribuable.nom) == b.proprietaire.strip().lower()))
    if not ctb:
        nc = s.scalar(select(func.count()).select_from(Contribuable)) + 1
        ctb = Contribuable(id_contribuable=f"CTB-{nc:05d}", nom=b.proprietaire.strip(),
                           type=b.type_contribuable, telephone=b.telephone, commune=b.commune)
        s.add(ctb)
    s.add(Bien(id_bien=id_bien, id_contribuable=ctb.id_contribuable, commune=b.commune,
               quartier=b.quartier, avenue=b.avenue.strip(), type_bien=b.type_bien, usage=b.usage,
               nb_logements=b.nb_logements, occupation=b.occupation, lat=b.lat, lon=b.lon))
    log(s, u, "Création d'un bien", id_bien, "-", b.avenue)
    s.commit()
    return {"id_bien": id_bien}


@app.patch("/biens/{id_bien}/statut")
def changer_statut(id_bien: str, body: StatutIn, u: Utilisateur = Depends(require("update")),
                   s: Session = Depends(get_db)):
    b = s.get(Bien, id_bien) or (_ for _ in ()).throw(HTTPException(404, "Bien introuvable"))
    check_scope(u, b.commune)
    if PERMS[u.role]["update"] == "limitée" and (body.statut != "En vérification" or b.statut == "Actif"):
        raise HTTPException(403, "Modification limitée au statut « En vérification »")
    ancien, b.statut = b.statut, body.statut
    log(s, u, "Modification du statut d'un bien", id_bien, ancien, body.statut)
    s.commit()
    return {"id_bien": id_bien, "statut": b.statut}


@app.delete("/biens/{id_bien}")
def supprimer_bien(id_bien: str, u: Utilisateur = Depends(require("delete")), s: Session = Depends(get_db)):
    b = s.get(Bien, id_bien) or (_ for _ in ()).throw(HTTPException(404, "Bien introuvable"))
    check_scope(u, b.commune)
    if PERMS[u.role]["delete"] == "limitée" and b.statut != "Inactif":
        raise HTTPException(403, "Suppression limitée aux biens « Inactif »")
    if s.scalar(select(func.count()).select_from(Declaration).where(Declaration.id_bien == id_bien)):
        raise HTTPException(409, "Bien lié à des déclarations : passez-le à « Inactif » au lieu de le supprimer")
    log(s, u, "Suppression d'un bien", id_bien, b.avenue, "supprimé")
    s.delete(b)
    s.commit()
    return {"supprime": id_bien}


@app.post("/declarations", status_code=201)
def creer_declaration(d: DeclarationIn, u: Utilisateur = Depends(require("create")),
                      s: Session = Depends(get_db)):
    b = s.get(Bien, d.id_bien) or (_ for _ in ()).throw(HTTPException(404, "Bien introuvable"))
    check_scope(u, b.commune)
    if s.scalar(select(Declaration).where(Declaration.id_bien == d.id_bien, Declaration.periode == d.periode)):
        raise HTTPException(409, "Déclaration déjà existante pour ce bien et cette période")
    taux = get_taux(s, b.usage)
    du = round(d.loyer_annuel_declare * taux / 100, 2)
    n = s.scalar(select(func.count()).select_from(Declaration)) + 1
    ref = f"DEC-{d.periode}-{n:05d}"
    s.add(Declaration(ref=ref, id_bien=d.id_bien, periode=d.periode, loyer_annuel_declare=d.loyer_annuel_declare,
                      taux_applique=taux, montant_du=du, date=date.today(), canal=d.canal))
    log(s, u, "Création d'une déclaration", ref, "-", f"loyer {d.loyer_annuel_declare} / taux {taux} / dû {du}")
    s.commit()
    return {"ref": ref, "taux_applique": taux, "montant_du": du}


def solde_decl(s: Session, ref: str):
    d = s.get(Declaration, ref)
    if not d:
        raise HTTPException(404, "Déclaration introuvable")
    paye = s.scalar(select(func.coalesce(func.sum(Paiement.montant), 0)).where(
        Paiement.ref_decl == ref, Paiement.confirme.is_(True)))
    return d, float(paye), round(float(d.montant_du) - float(paye), 2)


@app.get("/dossiers")
def dossiers(u: Utilisateur = Depends(require("read")), s: Session = Depends(get_db)):
    q = select(Declaration, Bien).join(Bien, Bien.id_bien == Declaration.id_bien)
    if u.commune:
        q = q.where(Bien.commune == u.commune)
    out = []
    for d, b in s.execute(q).all():
        _, paye, solde = solde_decl(s, d.ref)
        out.append(dict(ref=d.ref, id_bien=d.id_bien, commune=b.commune, du=float(d.montant_du), paye=paye,
                        solde=solde, statut_paiement="Soldé" if solde <= 0.005 else ("Partiel" if paye > 0 else "Impayé")))
    return out


@app.post("/paiements", status_code=201)
def creer_paiement(p: PaiementIn, u: Utilisateur = Depends(require("create")), s: Session = Depends(get_db)):
    d, _, solde = solde_decl(s, p.ref_decl)
    check_scope(u, s.get(Bien, d.id_bien).commune)
    if p.montant > solde + 0.005:
        raise HTTPException(409, f"Montant supérieur au solde dû ({solde})")
    n = s.scalar(select(func.count()).select_from(Paiement)) + 1
    ref = f"PAY-{n:06d}"
    s.add(Paiement(ref_paiement=ref, ref_decl=p.ref_decl, montant=p.montant, date=date.today(),
                   canal=p.canal, confirme=p.confirme))
    log(s, u, "Enregistrement d'un paiement", ref, "-", f"{p.montant} via {p.canal} (confirmé={p.confirme})")
    s.commit()
    return {"ref_paiement": ref, "code_verification": doc_code(ref, p.ref_decl, p.montant) if p.confirme else None}


@app.post("/paiements/{ref}/confirmer")
def confirmer_paiement(ref: str, u: Utilisateur = Depends(require("update")), s: Session = Depends(get_db)):
    p = s.get(Paiement, ref) or (_ for _ in ()).throw(HTTPException(404, "Paiement introuvable"))
    d = s.get(Declaration, p.ref_decl)
    check_scope(u, s.get(Bien, d.id_bien).commune)
    p.confirme = True
    log(s, u, "Confirmation d'un paiement", ref, "non confirmé", "confirmé")
    s.commit()
    return {"ref_paiement": ref, "code_verification": doc_code(ref, p.ref_decl, p.montant)}


@app.get("/verification/{ref_paiement}/{code}")
def verifier(ref_paiement: str, code: str, s: Session = Depends(get_db)):
    """Endpoint public (scan du QR) : authentique / non retrouvé / vérification requise."""
    p = s.get(Paiement, ref_paiement)
    if not p:
        return {"resultat": "non_retrouve", "feu": "rouge"}
    if p.confirme and hmac.compare_digest(code.upper(), doc_code(p.ref_paiement, p.ref_decl, p.montant)):
        return {"resultat": "authentique", "feu": "vert", "ref_decl": p.ref_decl,
                "montant": float(p.montant), "date": p.date}
    return {"resultat": "verification_requise", "feu": "orange"}


@app.get("/stats")
def stats(u: Utilisateur = Depends(require("read")), s: Session = Depends(get_db)):
    doss = dossiers(u, s)
    du, paye = sum(d["du"] for d in doss), sum(d["paye"] for d in doss)
    pot = s.get(Parametre, "potentiel_estime")
    nb_biens = len(liste_biens(None, u, s))
    return dict(biens=nb_biens, declarations=len(doss), total_du=du, recettes_confirmees=paye,
                arrieres=max(du - paye, 0), taux_recouvrement=round(paye / du * 100, 1) if du else 0,
                couverture_potentiel=round(min(nb_biens / float(pot.valeur) * 100, 100), 1) if pot else None)


@app.get("/parametres")
def lire_parametres(u: Utilisateur = Depends(require("read")), s: Session = Depends(get_db)):
    return {p.cle: p.valeur for p in s.scalars(select(Parametre)).all()}


@app.put("/parametres")
def maj_parametres(body: ParametresIn, u: Utilisateur = Depends(current_user), s: Session = Depends(get_db)):
    if u.role != "Administrateur":
        raise HTTPException(403, "Réservé à l'administrateur provincial")
    for usage, taux in body.taux.items():
        cle = f"taux:{usage}"
        p = s.get(Parametre, cle)
        log(s, u, "Modification d'un paramètre légal", cle, p.valeur if p else "-", taux)
        if p:
            p.valeur = str(taux)
        else:
            s.add(Parametre(cle=cle, valeur=str(taux)))
    s.commit()
    return {"ok": True}


@app.get("/audit")
def journal(limit: int = 200, u: Utilisateur = Depends(current_user), s: Session = Depends(get_db)):
    if u.role not in ("Administrateur", "Auditeur", "Direction DPMER"):
        raise HTTPException(403, "Accès au journal non autorisé")
    return s.scalars(select(Audit).order_by(Audit.id.desc()).limit(limit)).all()
