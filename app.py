"""
SUD-KIVU IRL DIGITAL
Plateforme numérique provinciale de gestion de l'impôt sur le revenu locatif.
Prototype Streamlit basé sur le cahier des charges (DPMER - Sud-Kivu, 2026).

Lancer :  streamlit run app.py

IMPORTANT : les taux d'imposition de ce prototype sont des PARAMÈTRES FICTIFS.
Le système ne remplace pas la loi : les taux, exonérations et pénalités
doivent être fixés par les textes légaux et validés par les autorités.
"""

import hashlib
import io
import random
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

try:  # QR code facultatif
    import qrcode
except Exception:  # pragma: no cover
    qrcode = None

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SUD-KIVU IRL DIGITAL",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SECRET = "SK-IRL-2026-CLE-DEMO"  # à remplacer par une vraie clé secrète côté serveur
TODAY = date.today()

CSS = """
<style>
.block-container {padding-top: 1.5rem;}
.hero {background: linear-gradient(120deg,#0b3d2e,#1b7f5c); color:white;
       padding:1.2rem 1.5rem; border-radius:14px; margin-bottom:1rem;}
.hero h1 {margin:0; font-size:1.7rem; color:white;}
.hero p {margin:.2rem 0 0 0; opacity:.9;}
div[data-testid="stMetric"] {background:#f4f8f6; border:1px solid #d9e8e1;
       padding:.8rem 1rem; border-radius:12px;}
div[data-testid="stMetricValue"] {color:#0b3d2e;}
.badge-ok {background:#d8f5e3; color:#116b36; padding:.5rem 1rem; border-radius:10px; font-weight:600;}
.badge-ko {background:#fde0e0; color:#a11818; padding:.5rem 1rem; border-radius:10px; font-weight:600;}
.badge-warn {background:#ffecd1; color:#a15c00; padding:.5rem 1rem; border-radius:10px; font-weight:600;}
.small {font-size:.85rem; opacity:.75;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# UTILISATEURS ET DROITS (RBAC)
# ---------------------------------------------------------------------------
def h(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


# identifiant: (hash mdp, nom affiché, rôle, commune de rattachement ou None)
USERS = {
    "admin": (h("admin123"), "Administrateur provincial", "Administrateur", None),
    "direction": (h("dpmer123"), "Direction DPMER", "Direction DPMER", None),
    "chef.mul": (h("chef123"), "Chef de centre Mulongwe", "Chef de centre", "Mulongwe"),
    "agent024": (h("agent123"), "Agent 024 (identification)", "Agent d'identification", "Kalundu"),
    "controleur": (h("ctrl123"), "Agent de contrôle", "Agent de contrôle", None),
    "recouvrement": (h("recou123"), "Agent de recouvrement", "Agent de recouvrement", None),
    "finance": (h("fin123"), "Responsable financier", "Responsable financier", None),
    "auditeur": (h("audit123"), "Auditeur autorisé", "Auditeur", None),
}

# lecture / création / modification / suppression  (True, False, "limitée", "politique")
PERMS = {
    "Administrateur": dict(read=True, create=True, update=True, delete="politique"),
    "Direction DPMER": dict(read=True, create=False, update=False, delete=False),
    "Chef de centre": dict(read=True, create=True, update=True, delete="limitée"),
    "Agent d'identification": dict(read=True, create=True, update="limitée", delete=False),
    "Agent de contrôle": dict(read=True, create=True, update=True, delete=False),
    "Agent de recouvrement": dict(read=True, create=True, update="limitée", delete=False),
    "Responsable financier": dict(read=True, create=False, update=False, delete=False),
    "Auditeur": dict(read=True, create=False, update=False, delete=False),
}

PAGES_ALL = [
    "📊 Tableau de bord",
    "🏠 Registre des biens",
    "📄 Contrats",
    "🧾 Déclarations & calcul",
    "💳 Paiements & quittances",
    "🔎 Contrôle & alertes",
    "💰 Recouvrement",
    "🗺️ Carte & zones",
    "✅ Vérification QR",
    "⚙️ Paramètres",
    "🛡️ Journal d'audit",
]
PAGES_BY_ROLE = {
    "Administrateur": PAGES_ALL,
    "Direction DPMER": [p for p in PAGES_ALL if "Paramètres" not in p],
    "Chef de centre": [p for p in PAGES_ALL if "Paramètres" not in p and "audit" not in p],
    "Agent d'identification": ["🏠 Registre des biens", "📄 Contrats", "🧾 Déclarations & calcul",
                               "🗺️ Carte & zones", "✅ Vérification QR"],
    "Agent de contrôle": ["📊 Tableau de bord", "🏠 Registre des biens", "📄 Contrats",
                          "🔎 Contrôle & alertes", "🗺️ Carte & zones", "✅ Vérification QR"],
    "Agent de recouvrement": ["💳 Paiements & quittances", "💰 Recouvrement", "✅ Vérification QR"],
    "Responsable financier": ["📊 Tableau de bord", "💰 Recouvrement", "🗺️ Carte & zones",
                              "✅ Vérification QR"],
    "Auditeur": ["📊 Tableau de bord", "🛡️ Journal d'audit", "✅ Vérification QR"],
}


# ---------------------------------------------------------------------------
# DONNÉES DE DÉMONSTRATION
# ---------------------------------------------------------------------------
COMMUNES = {
    "Mulongwe": ("MUL", -3.3880, 29.1260, ["Mulongwe Centre", "Songo", "Kasenga"]),
    "Kalundu": ("KAL", -3.4120, 29.1450, ["Kalundu Port", "Kilibula", "Mukuwa"]),
    "Kavimvira": ("KAV", -3.3480, 29.1550, ["Kavimvira Centre", "Kasenga Nord", "Rubuye"]),
}
USAGES = ["Habitation", "Commercial", "Mixte"]
TYPES_BIEN = ["Maison", "Appartement", "Immeuble", "Boutique / local"]
NOMS = ["Amani", "Baraka", "Chirimwami", "Furaha", "Kabila", "Lukamba", "Mbilizi", "Ngabo",
        "Mushagalusa", "Zawadi", "Bahati", "Cibalonza", "Masumbuko", "Nyota", "Safari", "Tshiala"]
PRENOMS = ["Jean", "Marie", "Pascal", "Esther", "Joseph", "Claudine", "Patient", "Générose",
           "Elie", "Rachel", "David", "Sifa", "Trésor", "Dorcas"]
CANAUX = ["Banque agréée", "Mobile money agréé", "Caisse DPMER"]
DEFAULT_PARAMS = {
    # PARAMÈTRES FICTIFS : à remplacer par les valeurs légales approuvées
    "taux": {"Habitation": 10.0, "Commercial": 15.0, "Mixte": 12.0},
    "devise": "USD",
    "potentiel_estime": 220,
}


def quittance_code(ref_paiement: str, ref_decl: str, montant: float) -> str:
    raw = f"{ref_paiement}|{ref_decl}|{montant:.2f}|{SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def generate_db() -> dict:
    rnd = random.Random(2026)
    contribuables, biens, contrats, decls, paiements = [], [], [], [], []
    compteurs = {c: 0 for c in COMMUNES}

    for i in range(1, 71):
        commune = rnd.choice(list(COMMUNES))
        contribuables.append(dict(
            id_contribuable=f"CTB-{i:05d}",
            nom=f"{rnd.choice(PRENOMS)} {rnd.choice(NOMS)}",
            type=rnd.choice(["Personne physique"] * 5 + ["Personne morale"]),
            telephone=f"+243 8{rnd.randint(1, 9)}{rnd.randint(1000000, 9999999)}",
            commune=commune,
        ))

    for _ in range(115):
        ctb = rnd.choice(contribuables)
        commune = ctb["commune"] if rnd.random() < .8 else rnd.choice(list(COMMUNES))
        code, lat, lon, quartiers = COMMUNES[commune]
        compteurs[commune] += 1
        id_bien = f"SK-IRL-UVI-{code}-{compteurs[commune]:06d}"
        usage = rnd.choice(USAGES)
        statut_occ = rnd.choice(["Occupé"] * 6 + ["Vacant"])
        statut = rnd.choice(["Actif"] * 8 + ["En vérification", "Inactif"])
        biens.append(dict(
            id_bien=id_bien, id_contribuable=ctb["id_contribuable"], proprietaire=ctb["nom"],
            commune=commune, quartier=rnd.choice(quartiers),
            avenue=f"Avenue {rnd.choice(NOMS)} n°{rnd.randint(1, 80)}",
            type_bien=rnd.choice(TYPES_BIEN), usage=usage,
            nb_logements=rnd.randint(1, 6), occupation=statut_occ, statut=statut,
            lat=lat + rnd.uniform(-.012, .012), lon=lon + rnd.uniform(-.012, .012),
        ))

    base = date(2026, 1, 10)
    span = max((TODAY - base).days, 60)
    n_decl = n_pay = n_ctr = 0
    for b in biens:
        loyer = rnd.choice([40, 60, 80, 120, 150, 200, 300, 450, 600])
        if b["occupation"] == "Occupé" and rnd.random() < .9:
            n_ctr += 1
            debut = TODAY - timedelta(days=rnd.randint(60, 700))
            fin = TODAY + timedelta(days=rnd.randint(-30, 400))
            contrats.append(dict(
                id_contrat=f"CTR-{n_ctr:05d}", id_bien=b["id_bien"], commune=b["commune"],
                locataire=f"{rnd.choice(PRENOMS)} {rnd.choice(NOMS)}", loyer_mensuel=float(loyer),
                periodicite="Mensuelle", debut=debut, fin=fin))
        if rnd.random() < .85:
            n_decl += 1
            ref = f"DEC-2026-{n_decl:05d}"
            declare = loyer * 12 * (rnd.uniform(.55, .9) if rnd.random() < .12 else 1)
            decls.append(dict(
                ref=ref, id_bien=b["id_bien"], periode=2026,
                loyer_annuel_declare=round(declare, 2),
                date=base + timedelta(days=rnd.randint(0, span)),
                statut=rnd.choice(["Validée"] * 5 + ["Soumise", "À corriger"]),
                canal=rnd.choice(["Agent terrain", "Portail contribuable", "Centre"])))
    d_df = pd.DataFrame(decls)
    taux = DEFAULT_PARAMS["taux"]
    usage_map = {b["id_bien"]: b["usage"] for b in biens}
    commune_map = {b["id_bien"]: b["commune"] for b in biens}
    for _, d in d_df.iterrows():
        r = rnd.random()
        if r < .25:
            continue  # aucun paiement
        du = d["loyer_annuel_declare"] * taux[usage_map[d["id_bien"]]] / 100
        parts = [1.0] if r < .65 else [rnd.uniform(.3, .7)]
        for p in parts:
            n_pay += 1
            ref_p = f"PAY-{n_pay:06d}"
            montant = round(du * p, 2)
            paiements.append(dict(
                ref_paiement=ref_p, ref_decl=d["ref"], commune=commune_map[d["id_bien"]],
                montant=montant, date=d["date"] + timedelta(days=rnd.randint(1, 40)),
                canal=rnd.choice(CANAUX), confirme=rnd.random() > .08))

    return dict(
        contribuables=pd.DataFrame(contribuables), biens=pd.DataFrame(biens),
        contrats=pd.DataFrame(contrats), declarations=d_df,
        paiements=pd.DataFrame(paiements),
        audit=[dict(horodatage=datetime.now().strftime("%d/%m/%Y %H:%M:%S"), utilisateur="système",
                    action="Initialisation des données de démonstration", dossier="-",
                    ancienne="-", nouvelle=f"{len(biens)} biens")],
        params={"taux": dict(taux), "devise": DEFAULT_PARAMS["devise"],
                "potentiel_estime": DEFAULT_PARAMS["potentiel_estime"]},
    )


def db() -> dict:
    if "db" not in st.session_state:
        st.session_state["db"] = generate_db()
    return st.session_state["db"]


# ---------------------------------------------------------------------------
# OUTILS
# ---------------------------------------------------------------------------
def log(action: str, dossier: str = "-", ancienne: str = "-", nouvelle: str = "-"):
    user = st.session_state["user"]
    db()["audit"].insert(0, dict(
        horodatage=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        utilisateur=f"{user['nom']} ({user['login']})", action=action,
        dossier=dossier, ancienne=str(ancienne), nouvelle=str(nouvelle)))


def perm(action: str):
    return PERMS[st.session_state["user"]["role"]][action]


def can(action: str) -> bool:
    return bool(perm(action))


def scope(df: pd.DataFrame, col: str = "commune") -> pd.DataFrame:
    """Restreint les données au ressort de l'utilisateur (ex. chef de centre)."""
    c = st.session_state["user"]["commune"]
    if c and col in df.columns:
        return df[df[col] == c]
    return df


def money(x: float) -> str:
    return f"{x:,.0f} {db()['params']['devise']}".replace(",", " ")


def dossiers() -> pd.DataFrame:
    """Dossiers IRL : déclaration + montant dû + payé + solde."""
    data = db()
    d = data["declarations"].copy()
    if d.empty:
        return pd.DataFrame(columns=["ref", "id_bien", "commune", "usage", "du", "paye",
                                     "solde", "statut_paiement", "contribuable"])
    b = data["biens"][["id_bien", "commune", "usage", "proprietaire", "quartier"]]
    d = d.merge(b, on="id_bien", how="left")
    d["taux"] = d["usage"].map(data["params"]["taux"]).fillna(0.0)
    d["du"] = (d["loyer_annuel_declare"] * d["taux"] / 100).round(2)
    p = data["paiements"]
    paid = p[p["confirme"]].groupby("ref_decl")["montant"].sum() if not p.empty else pd.Series(dtype=float)
    d["paye"] = d["ref"].map(paid).fillna(0.0).round(2)
    d["solde"] = (d["du"] - d["paye"]).round(2)
    d["statut_paiement"] = np.select(
        [d["solde"] <= 0.005, d["paye"] > 0], ["Soldé", "Partiel"], default="Impayé")
    d["contribuable"] = d["proprietaire"]
    return scope(d)


def alertes() -> pd.DataFrame:
    """Alertes d'aide au contrôle. L'algorithme ne sanctionne personne."""
    data = db()
    biens = scope(data["biens"])
    decl = data["declarations"]
    ctr = data["contrats"]
    dos = dossiers()
    out = []

    sans_decl = biens[~biens["id_bien"].isin(decl["id_bien"])]
    for _, r in sans_decl.iterrows():
        out.append(("Déclaration manquante", r["id_bien"], r["commune"],
                    f"Bien {r['statut'].lower()} sans déclaration 2026", "Moyenne"))

    occ = biens[biens["occupation"] == "Occupé"]
    for _, r in occ[~occ["id_bien"].isin(ctr["id_bien"])].iterrows():
        out.append(("Contrat absent", r["id_bien"], r["commune"],
                    "Bien occupé sans contrat de bail enregistré", "Moyenne"))

    ctr_s = scope(ctr)
    for _, r in ctr_s.iterrows():
        jours = (r["fin"] - TODAY).days
        if 0 <= jours <= 60:
            out.append(("Contrat arrivant à échéance", r["id_bien"], r["commune"],
                        f"Contrat {r['id_contrat']} expire dans {jours} jours", "Faible"))
        elif jours < 0:
            out.append(("Contrat expiré", r["id_bien"], r["commune"],
                        f"Contrat {r['id_contrat']} expiré depuis {-jours} jours", "Moyenne"))

    if not dos.empty:
        for _, r in dos[dos["statut_paiement"] == "Impayé"].iterrows():
            out.append(("Paiement attendu non confirmé", r["id_bien"], r["commune"],
                        f"{r['ref']} : {money(r['du'])} dû, aucun paiement confirmé", "Élevée"))
        m = dos.merge(ctr[["id_bien", "loyer_mensuel"]], on="id_bien", how="inner")
        for _, r in m.iterrows():
            attendu = r["loyer_mensuel"] * 12
            if r["loyer_annuel_declare"] < 0.9 * attendu:
                out.append(("Incohérence loyer déclaré / contrat", r["id_bien"], r["commune"],
                            f"Déclaré {r['loyer_annuel_declare']:.0f} vs contrat {attendu:.0f} /an",
                            "Élevée"))
    cols = ["Type d'alerte", "Bien", "Commune", "Détail", "Priorité"]
    return pd.DataFrame(out, columns=cols)


def header(titre: str, sous_titre: str = ""):
    st.markdown(f'<div class="hero"><h1>{titre}</h1><p>{sous_titre}</p></div>',
                unsafe_allow_html=True)


def csv_button(df: pd.DataFrame, nom: str, label: str = "⬇️ Exporter en CSV"):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=nom, mime="text/csv")


# ---------------------------------------------------------------------------
# PAGES
# ---------------------------------------------------------------------------
def page_dashboard():
    header("Tableau de bord provincial",
           "Identifier – Fiabiliser – Recouvrer – Développer")
    data = db()
    dos = dossiers()
    biens = scope(data["biens"])
    ctb = scope(data["contribuables"])
    total_du = dos["du"].sum() if not dos.empty else 0
    total_paye = dos["paye"].sum() if not dos.empty else 0
    arrieres = max(total_du - total_paye, 0)
    taux_rec = (total_paye / total_du * 100) if total_du else 0
    potentiel = data["params"]["potentiel_estime"]
    couverture = min(len(biens) / potentiel * 100, 100) if potentiel else 0

    c = st.columns(4)
    c[0].metric("Contribuables enregistrés", f"{len(ctb):,}".replace(",", " "))
    c[1].metric("Biens enregistrés", f"{len(biens):,}".replace(",", " "))
    c[2].metric("Déclarations", f"{len(dos):,}".replace(",", " "))
    c[3].metric("Recettes confirmées", money(total_paye))
    c = st.columns(4)
    c[0].metric("Montant total dû", money(total_du))
    c[1].metric("Arriérés", money(arrieres))
    c[2].metric("Taux de recouvrement", f"{taux_rec:.1f} %")
    c[3].metric("Couverture numérique du potentiel", f"{couverture:.1f} %",
                help="Biens correctement enregistrés / estimation du nombre total de biens locatifs")
    st.progress(min(couverture / 100, 1.0), text="Indicateur stratégique central : couverture du potentiel IRL")

    if dos.empty:
        st.info("Aucun dossier disponible dans votre périmètre.")
        return
    left, right = st.columns(2)
    with left:
        st.subheader("Recettes confirmées vs arriérés par commune")
        g = dos.groupby("commune").agg(Payé=("paye", "sum"), Solde=("solde", "sum"))
        g["Solde"] = g["Solde"].clip(lower=0)
        st.bar_chart(g)
    with right:
        st.subheader("Répartition des dossiers")
        st.bar_chart(dos["statut_paiement"].value_counts())
    st.subheader("Évolution mensuelle des recettes confirmées")
    p = scope(data["paiements"])
    p = p[p["confirme"]].copy()
    if not p.empty:
        p["mois"] = pd.to_datetime(p["date"]).dt.to_period("M").astype(str)
        st.line_chart(p.groupby("mois")["montant"].sum())
    st.caption("Données de démonstration générées automatiquement : ce ne sont pas des statistiques réelles.")


def page_registre():
    header("Registre provincial des biens locatifs",
           "Bien ↔ Propriétaire ↔ Localisation ↔ Contrat ↔ Déclaration ↔ Paiement ↔ Historique")
    data = db()
    biens = scope(data["biens"])

    f = st.columns(5)
    commune = f[0].selectbox("Commune", ["Toutes"] + list(COMMUNES))
    usage = f[1].selectbox("Usage", ["Tous"] + USAGES)
    statut = f[2].selectbox("Statut", ["Tous", "Actif", "En vérification", "Inactif"])
    occ = f[3].selectbox("Occupation", ["Tous", "Occupé", "Vacant"])
    q = f[4].text_input("Recherche (ID, propriétaire, avenue)")
    v = biens
    if commune != "Toutes":
        v = v[v["commune"] == commune]
    if usage != "Tous":
        v = v[v["usage"] == usage]
    if statut != "Tous":
        v = v[v["statut"] == statut]
    if occ != "Tous":
        v = v[v["occupation"] == occ]
    if q:
        ql = q.lower()
        v = v[v.apply(lambda r: ql in f"{r['id_bien']} {r['proprietaire']} {r['avenue']}".lower(), axis=1)]
    st.caption(f"{len(v)} bien(s) affiché(s)")
    st.dataframe(v.drop(columns=["lat", "lon", "id_contribuable"]), hide_index=True)
    csv_button(v, "registre_biens.csv")

    tabs = st.tabs(["📁 Fiche du bien", "➕ Nouveau bien", "✏️ Modifier / supprimer"])
    with tabs[0]:
        if v.empty:
            st.info("Aucun bien.")
        else:
            sel = st.selectbox("Choisir un bien", v["id_bien"], key="fiche_bien")
            b = data["biens"].set_index("id_bien").loc[sel]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Identification**")
                st.write(f"Numéro : `{sel}`  \nPropriétaire : {b['proprietaire']}  \n"
                         f"Contribuable : {b['id_contribuable']}  \nStatut : {b['statut']}")
                st.markdown("**Caractéristiques**")
                st.write(f"Type : {b['type_bien']}  \nUsage : {b['usage']}  \n"
                         f"Logements : {b['nb_logements']}  \nOccupation : {b['occupation']}")
            with c2:
                st.markdown("**Localisation**")
                st.write(f"Province : Sud-Kivu  \nVille : Uvira  \nCommune : {b['commune']}  \n"
                         f"Quartier : {b['quartier']}  \n{b['avenue']}  \n"
                         f"GPS : {b['lat']:.5f}, {b['lon']:.5f}")
                ctr = data["contrats"][data["contrats"]["id_bien"] == sel]
                st.markdown("**Contrat**")
                if ctr.empty:
                    st.warning("Aucun contrat enregistré")
                else:
                    r = ctr.iloc[0]
                    st.write(f"{r['id_contrat']} – locataire {r['locataire']}  \n"
                             f"Loyer : {r['loyer_mensuel']:.0f} / mois – du {r['debut']} au {r['fin']}")
            dos = dossiers()
            dd = dos[dos["id_bien"] == sel] if not dos.empty else dos
            st.markdown("**Historique fiscal**")
            if dd.empty:
                st.info("Aucune déclaration pour ce bien.")
            else:
                st.dataframe(dd[["ref", "periode", "loyer_annuel_declare", "du", "paye", "solde",
                                 "statut_paiement"]], hide_index=True)
            hist = [a for a in data["audit"] if a["dossier"] == sel]
            if hist:
                st.markdown("**Journal des modifications**")
                st.dataframe(pd.DataFrame(hist), hide_index=True)
    with tabs[1]:
        if not can("create"):
            st.info("Votre rôle ne permet pas de créer un bien.")
        else:
            with st.form("new_bien", clear_on_submit=True):
                c1, c2 = st.columns(2)
                owner = c1.text_input("Nom du propriétaire *")
                tel = c1.text_input("Téléphone")
                types_p = c1.selectbox("Type de contribuable", ["Personne physique", "Personne morale"])
                allowed = [st.session_state["user"]["commune"]] if st.session_state["user"]["commune"] else list(COMMUNES)
                com = c2.selectbox("Commune", allowed)
                quartier = c2.selectbox("Quartier", COMMUNES[com][3])
                avenue = c2.text_input("Avenue / n° *")
                c3, c4, c5, c6 = st.columns(4)
                tb = c3.selectbox("Type de bâtiment", TYPES_BIEN)
                us = c4.selectbox("Usage", USAGES)
                nb = c5.number_input("Nb de logements", 1, 100, 1)
                oc = c6.selectbox("Occupation", ["Occupé", "Vacant"])
                base_lat, base_lon = COMMUNES[com][1], COMMUNES[com][2]
                g1, g2 = st.columns(2)
                lat = g1.number_input("Latitude", value=float(base_lat), format="%.5f")
                lon = g2.number_input("Longitude", value=float(base_lon), format="%.5f")
                ok = st.form_submit_button("Enregistrer le bien", type="primary")
            if ok:
                if not owner.strip() or not avenue.strip():
                    st.error("Le propriétaire et l'avenue sont obligatoires.")
                else:
                    dup = data["biens"][(data["biens"]["proprietaire"].str.lower() == owner.strip().lower())
                                        & (data["biens"]["avenue"].str.lower() == avenue.strip().lower())]
                    if not dup.empty:
                        st.warning(f"Doublon possible : {dup.iloc[0]['id_bien']} existe déjà avec ces informations.")
                    else:
                        code = COMMUNES[com][0]
                        n = (data["biens"]["commune"] == com).sum() + 1
                        id_bien = f"SK-IRL-UVI-{code}-{n:06d}"
                        ex = data["contribuables"][data["contribuables"]["nom"].str.lower() == owner.strip().lower()]
                        if ex.empty:
                            id_c = f"CTB-{len(data['contribuables']) + 1:05d}"
                            data["contribuables"] = pd.concat([data["contribuables"], pd.DataFrame([dict(
                                id_contribuable=id_c, nom=owner.strip(), type=types_p,
                                telephone=tel, commune=com)])], ignore_index=True)
                        else:
                            id_c = ex.iloc[0]["id_contribuable"]
                        data["biens"] = pd.concat([data["biens"], pd.DataFrame([dict(
                            id_bien=id_bien, id_contribuable=id_c, proprietaire=owner.strip(),
                            commune=com, quartier=quartier, avenue=avenue.strip(), type_bien=tb,
                            usage=us, nb_logements=int(nb), occupation=oc, statut="En vérification",
                            lat=lat, lon=lon)])], ignore_index=True)
                        log("Création d'un bien", id_bien, "-", f"{owner.strip()} / {avenue.strip()}")
                        st.success(f"Bien créé avec l'identifiant {id_bien} (statut : En vérification).")
    with tabs[2]:
        if not (can("update") or can("delete")):
            st.info("Votre rôle est en lecture seule.")
        elif v.empty:
            st.info("Aucun bien.")
        else:
            sel = st.selectbox("Bien à traiter", v["id_bien"], key="mod_bien")
            cur = data["biens"].set_index("id_bien").loc[sel]
            if can("update"):
                opts = ["Actif", "En vérification", "Inactif"]
                if perm("update") == "limitée":
                    st.caption("Modification limitée : vous ne pouvez changer que le statut « En vérification ».")
                    opts = ["En vérification"] if cur["statut"] != "Actif" else []
                if opts:
                    new_s = st.selectbox("Nouveau statut", opts)
                    if st.button("Appliquer la modification"):
                        data["biens"].loc[data["biens"]["id_bien"] == sel, "statut"] = new_s
                        log("Modification du statut d'un bien", sel, cur["statut"], new_s)
                        st.success("Modification enregistrée et journalisée.")
                        st.rerun()
                else:
                    st.info("Modification non autorisée sur ce bien pour votre rôle.")
            if can("delete"):
                st.divider()
                st.markdown("**Suppression**")
                if perm("delete") == "limitée" and cur["statut"] != "Inactif":
                    st.caption("Suppression limitée aux biens au statut « Inactif ».")
                else:
                    conf = st.checkbox("Je confirme la suppression de ce bien (action tracée)")
                    if st.button("Supprimer", disabled=not conf):
                        data["biens"] = data["biens"][data["biens"]["id_bien"] != sel]
                        log("Suppression d'un bien", sel, cur["proprietaire"], "supprimé")
                        st.success("Bien supprimé.")
                        st.rerun()


def page_contrats():
    header("Gestion des contrats de bail",
           "Propriétaire + bien + locataire + période + informations financières")
    data = db()
    ctr = scope(data["contrats"]).copy()
    if ctr.empty:
        st.info("Aucun contrat.")
    else:
        ctr["jours_restants"] = ctr["fin"].apply(lambda d: (d - TODAY).days)
        ctr["état"] = np.select([ctr["jours_restants"] < 0, ctr["jours_restants"] <= 60],
                                ["🔴 Expiré", "🟠 À échéance"], default="🟢 En cours")
        c = st.columns(3)
        c[0].metric("Contrats", len(ctr))
        c[1].metric("À échéance (≤ 60 j)", int((ctr["état"] == "🟠 À échéance").sum()))
        c[2].metric("Expirés", int((ctr["état"] == "🔴 Expiré").sum()))
        etat = st.multiselect("Filtrer par état", ctr["état"].unique(), default=list(ctr["état"].unique()))
        st.dataframe(ctr[ctr["état"].isin(etat)], hide_index=True)
        csv_button(ctr, "contrats.csv")

    if can("create"):
        st.subheader("➕ Enregistrer un contrat")
        biens = scope(data["biens"])
        with st.form("new_ctr", clear_on_submit=True):
            bien = st.selectbox("Bien", biens["id_bien"])
            c1, c2, c3 = st.columns(3)
            loc = c1.text_input("Locataire *")
            loyer = c2.number_input("Loyer mensuel", 0.0, 100000.0, 100.0, 10.0)
            per = c3.selectbox("Périodicité", ["Mensuelle", "Trimestrielle", "Annuelle"])
            d1, d2 = st.columns(2)
            debut = d1.date_input("Début", TODAY)
            fin = d2.date_input("Fin", TODAY + timedelta(days=365))
            ok = st.form_submit_button("Enregistrer", type="primary")
        if ok:
            if not loc.strip() or fin <= debut:
                st.error("Locataire obligatoire et date de fin postérieure au début.")
            else:
                n = len(data["contrats"]) + 1
                cm = data["biens"].set_index("id_bien").loc[bien, "commune"]
                data["contrats"] = pd.concat([data["contrats"], pd.DataFrame([dict(
                    id_contrat=f"CTR-{n:05d}", id_bien=bien, commune=cm, locataire=loc.strip(),
                    loyer_mensuel=float(loyer), periodicite=per, debut=debut, fin=fin)])], ignore_index=True)
                log("Création d'un contrat", bien, "-", f"CTR-{n:05d} / {loc.strip()} / {loyer}")
                st.success("Contrat enregistré.")
                st.rerun()


def page_declarations():
    header("Déclarations & moteur de calcul",
           "Paramètres légaux → type de bien → période → base imposable → montant à payer")
    data = db()
    taux = data["params"]["taux"]
    st.warning("Les taux utilisés sont des **paramètres fictifs de démonstration**. "
               "Le logiciel applique uniquement les paramètres légalement approuvés ; "
               "il ne décide ni du taux légal, ni des pénalités, ni des exonérations.")

    t1, t2, t3 = st.tabs(["📋 Déclarations", "➕ Nouvelle déclaration", "🧮 Simulateur"])
    with t1:
        dos = dossiers()
        if dos.empty:
            st.info("Aucune déclaration.")
        else:
            st.dataframe(dos[["ref", "id_bien", "contribuable", "commune", "periode",
                              "loyer_annuel_declare", "taux", "du", "statut", "canal", "date"]],
                         hide_index=True)
            csv_button(dos, "declarations.csv")
    with t2:
        if not can("create"):
            st.info("Votre rôle ne permet pas de créer une déclaration.")
        else:
            biens = scope(data["biens"])
            biens = biens[biens["statut"] != "Inactif"]
            with st.form("new_decl", clear_on_submit=False):
                bien = st.selectbox("Bien", biens["id_bien"])
                c1, c2, c3 = st.columns(3)
                periode = c1.number_input("Période (année)", 2020, 2100, 2026)
                loyer = c2.number_input("Loyer annuel déclaré", 0.0, 10_000_000.0, 1200.0, 50.0)
                canal = c3.selectbox("Canal", ["Agent terrain", "Portail contribuable", "Centre"])
                ok = st.form_submit_button("Enregistrer la déclaration", type="primary")
            if ok:
                dup = data["declarations"][(data["declarations"]["id_bien"] == bien)
                                           & (data["declarations"]["periode"] == periode)]
                if not dup.empty:
                    st.error(f"Une déclaration existe déjà pour ce bien et cette période ({dup.iloc[0]['ref']}).")
                else:
                    usage = data["biens"].set_index("id_bien").loc[bien, "usage"]
                    du = loyer * taux[usage] / 100
                    ref = f"DEC-{int(periode)}-{len(data['declarations']) + 1:05d}"
                    data["declarations"] = pd.concat([data["declarations"], pd.DataFrame([dict(
                        ref=ref, id_bien=bien, periode=int(periode), loyer_annuel_declare=float(loyer),
                        date=TODAY, statut="Soumise", canal=canal)])], ignore_index=True)
                    log("Création d'une déclaration", ref, "-", f"{bien} / loyer {loyer} / dû {du:.2f}")
                    st.success(f"Déclaration {ref} enregistrée. Montant dû calculé : {money(du)}")
    with t3:
        c1, c2, c3 = st.columns(3)
        usage = c1.selectbox("Type / usage du bien", USAGES, key="sim_usage")
        loyer_m = c2.number_input("Loyer mensuel", 0.0, 1_000_000.0, 100.0, 10.0, key="sim_loyer")
        mois = c3.slider("Nombre de mois", 1, 12, 12)
        base = loyer_m * mois
        dû = base * taux[usage] / 100
        st.markdown(f"""
| Étape | Valeur |
|---|---|
| Paramètre : taux appliqué ({usage}) | **{taux[usage]:.2f} %** |
| Base imposable | **{money(base)}** |
| Montant à payer | **{money(dû)}** |
""")


def page_paiements():
    header("Paiements & quittances",
           "Obligation → référence de paiement → paiement → confirmation → mise à jour → quittance")
    data = db()
    dos = dossiers()
    pay = scope(data["paiements"])

    t1, t2, t3 = st.tabs(["📒 Paiements", "➕ Enregistrer un paiement", "🧾 Quittances"])
    with t1:
        c = st.columns(3)
        c[0].metric("Confirmés", int(pay["confirme"].sum()) if not pay.empty else 0)
        c[1].metric("En attente de confirmation", int((~pay["confirme"]).sum()) if not pay.empty else 0)
        c[2].metric("Montant confirmé", money(pay.loc[pay["confirme"], "montant"].sum()) if not pay.empty else money(0))
        st.dataframe(pay.sort_values("date", ascending=False), hide_index=True)
        if can("update") and not pay.empty:
            pend = pay[~pay["confirme"]]
            if not pend.empty:
                st.markdown("**Confirmer un paiement** (uniquement après réception de la confirmation du canal officiel)")
                sel = st.selectbox("Paiement en attente", pend["ref_paiement"])
                if st.button("✅ Marquer comme confirmé"):
                    data["paiements"].loc[data["paiements"]["ref_paiement"] == sel, "confirme"] = True
                    log("Confirmation d'un paiement", sel, "non confirmé", "confirmé")
                    st.success("Paiement confirmé, dossier mis à jour.")
                    st.rerun()
    with t2:
        if not can("create"):
            st.info("Votre rôle ne permet pas d'enregistrer un paiement.")
        else:
            ouverts = dos[dos["solde"] > 0] if not dos.empty else dos
            if ouverts.empty:
                st.success("Aucun solde à payer dans votre périmètre.")
            else:
                with st.form("new_pay", clear_on_submit=True):
                    ref = st.selectbox(
                        "Dossier", ouverts["ref"],
                        format_func=lambda r: f"{r} – solde {ouverts.set_index('ref').loc[r, 'solde']:.2f}")
                    c1, c2 = st.columns(2)
                    montant = c1.number_input("Montant payé", 0.01, 10_000_000.0, 10.0, 5.0)
                    canal = c2.selectbox("Canal", CANAUX)
                    conf = st.checkbox("Confirmation reçue du canal officiellement reconnu")
                    ok = st.form_submit_button("Enregistrer le paiement", type="primary")
                if ok:
                    solde = ouverts.set_index("ref").loc[ref, "solde"]
                    if montant > solde + 0.005:
                        st.error(f"Le montant dépasse le solde dû ({solde:.2f}).")
                    else:
                        n = len(data["paiements"]) + 1
                        ref_p = f"PAY-{n:06d}"
                        cm = ouverts.set_index("ref").loc[ref, "commune"]
                        data["paiements"] = pd.concat([data["paiements"], pd.DataFrame([dict(
                            ref_paiement=ref_p, ref_decl=ref, commune=cm, montant=float(montant),
                            date=TODAY, canal=canal, confirme=bool(conf))])], ignore_index=True)
                        log("Enregistrement d'un paiement", ref_p, "-",
                            f"{montant} via {canal} ({'confirmé' if conf else 'en attente'})")
                        st.success(f"Paiement {ref_p} enregistré "
                                   f"({'confirmé' if conf else 'en attente de confirmation'}).")
    with t3:
        conf = pay[pay["confirme"]] if not pay.empty else pay
        if conf.empty:
            st.info("Aucun paiement confirmé.")
        else:
            sel = st.selectbox("Paiement confirmé", conf["ref_paiement"], key="quit_sel")
            r = conf.set_index("ref_paiement").loc[sel]
            code = quittance_code(sel, r["ref_decl"], r["montant"])
            payload = f"SKIRL|{sel}|{code}"
            c1, c2 = st.columns([2, 1])
            with c1:
                texte = (f"RÉPUBLIQUE DÉMOCRATIQUE DU CONGO – PROVINCE DU SUD-KIVU\n"
                         f"DPMER – QUITTANCE IRL\n{'-' * 44}\n"
                         f"Référence paiement : {sel}\nDossier : {r['ref_decl']}\n"
                         f"Montant : {r['montant']:.2f} {data['params']['devise']}\n"
                         f"Date : {r['date']}\nCanal : {r['canal']}\n"
                         f"Code de vérification : {code}\n")
                st.code(texte)
                st.download_button("⬇️ Télécharger la quittance", texte.encode("utf-8"),
                                   file_name=f"quittance_{sel}.txt")
            with c2:
                if qrcode:
                    buf = io.BytesIO()
                    qrcode.make(payload).save(buf, format="PNG")
                    st.image(buf.getvalue(), caption="QR de vérification")
                else:
                    st.info("Installez `qrcode[pil]` pour afficher le QR.")
                    st.code(payload)


def page_controle():
    header("Contrôle & alertes",
           "L'algorithme ne sanctionne personne : il aide l'agent à choisir les dossiers à vérifier")
    al = alertes()
    if al.empty:
        st.success("Aucune alerte dans votre périmètre.")
        return
    c = st.columns(4)
    c[0].metric("Alertes", len(al))
    c[1].metric("Priorité élevée", int((al["Priorité"] == "Élevée").sum()))
    c[2].metric("Priorité moyenne", int((al["Priorité"] == "Moyenne").sum()))
    c[3].metric("Priorité faible", int((al["Priorité"] == "Faible").sum()))
    f1, f2 = st.columns(2)
    types = f1.multiselect("Type d'alerte", sorted(al["Type d'alerte"].unique()),
                           default=sorted(al["Type d'alerte"].unique()))
    prio = f2.multiselect("Priorité", ["Élevée", "Moyenne", "Faible"], default=["Élevée", "Moyenne", "Faible"])
    v = al[al["Type d'alerte"].isin(types) & al["Priorité"].isin(prio)]
    order = {"Élevée": 0, "Moyenne": 1, "Faible": 2}
    v = v.sort_values("Priorité", key=lambda s: s.map(order))
    st.dataframe(v, hide_index=True)
    csv_button(v, "alertes_controle.csv")
    st.bar_chart(al["Type d'alerte"].value_counts())
    st.caption("Toute alerte nécessite une vérification humaine avant toute décision.")


def page_recouvrement():
    header("Recouvrement", "Total dû → Total payé → Solde → Retard → Actions de recouvrement")
    dos = dossiers()
    if dos.empty:
        st.info("Aucun dossier.")
        return
    c = st.columns(4)
    c[0].metric("Total dû", money(dos["du"].sum()))
    c[1].metric("Total payé", money(dos["paye"].sum()))
    c[2].metric("Solde", money(dos["solde"].clip(lower=0).sum()))
    c[3].metric("Dossiers impayés", int((dos["statut_paiement"] == "Impayé").sum()))
    stat = st.multiselect("Statut", ["Soldé", "Partiel", "Impayé"], default=["Partiel", "Impayé"])
    v = dos[dos["statut_paiement"].isin(stat)].copy()
    v["retard_jours"] = v["date"].apply(lambda d: max((TODAY - d).days - 30, 0))
    v = v.sort_values("solde", ascending=False)
    st.dataframe(
        v[["ref", "contribuable", "commune", "du", "paye", "solde", "statut_paiement", "retard_jours"]],
        hide_index=True,
        column_config={
            "du": st.column_config.NumberColumn("Dû", format="%.2f"),
            "paye": st.column_config.NumberColumn("Payé", format="%.2f"),
            "solde": st.column_config.NumberColumn("Solde", format="%.2f"),
        })
    csv_button(v, "recouvrement.csv")
    st.subheader("Soldes à recouvrer par commune")
    st.bar_chart(dos.groupby("commune")["solde"].sum().clip(lower=0))
    st.caption("Le retard est indicatif (délai de grâce de 30 jours fictif). "
               "Les pénalités éventuelles relèvent exclusivement des textes légaux.")


def page_carte():
    header("Carte & analyse géographique",
           "Province → Zone → Quartier → Bien")
    data = db()
    biens = scope(data["biens"])
    c1, c2 = st.columns(2)
    com = c1.selectbox("Commune", ["Toutes"] + list(COMMUNES))
    usg = c2.selectbox("Usage", ["Tous"] + USAGES)
    v = biens
    if com != "Toutes":
        v = v[v["commune"] == com]
    if usg != "Tous":
        v = v[v["usage"] == usg]
    st.map(v.rename(columns={"lat": "latitude", "lon": "longitude"})[["latitude", "longitude"]], zoom=12)
    st.caption(f"{len(v)} bien(s) géolocalisé(s). Les coordonnées ne sont collectées que lorsque c'est justifié.")

    dos = dossiers()
    st.subheader("Comparaison par zone")
    g = biens.groupby("commune").agg(Biens=("id_bien", "count"),
                                     Contribuables=("id_contribuable", "nunique"))
    if not dos.empty:
        d = dos.groupby("commune").agg(Recettes=("paye", "sum"), Arriérés=("solde", lambda s: s.clip(lower=0).sum()))
        g = g.join(d)
    g = g.fillna(0)
    pot = data["params"]["potentiel_estime"] / max(len(COMMUNES), 1)
    g["Couverture estimée (%)"] = (g["Biens"] / pot * 100).clip(upper=100).round(1)
    st.dataframe(g)
    st.info("Zones prioritaires de terrain : celles où la couverture estimée est la plus faible "
            "ou les arriérés les plus élevés.")


def page_qr():
    header("Vérification d'authenticité", "QR → serveur → vérification → résultat")
    data = db()
    st.write("Saisissez la référence et le code de la quittance (ou le contenu du QR : `SKIRL|PAY-xxxxxx|CODE`).")
    raw = st.text_input("Contenu du QR ou référence de paiement")
    code_in = st.text_input("Code de vérification (si référence saisie seule)")
    if st.button("Vérifier", type="primary"):
        ref_p, code = raw.strip(), code_in.strip().upper()
        if raw.startswith("SKIRL|"):
            parts = raw.split("|")
            if len(parts) == 3:
                ref_p, code = parts[1].strip(), parts[2].strip().upper()
        pay = data["paiements"]
        row = pay[pay["ref_paiement"] == ref_p]
        if row.empty:
            st.markdown('<div class="badge-ko">🔴 Document non retrouvé</div>', unsafe_allow_html=True)
        else:
            r = row.iloc[0]
            attendu = quittance_code(r["ref_paiement"], r["ref_decl"], r["montant"])
            if r["confirme"] and code == attendu:
                st.markdown('<div class="badge-ok">🟢 Document authentique</div>', unsafe_allow_html=True)
                st.write(f"Paiement {r['ref_paiement']} – dossier {r['ref_decl']} – "
                         f"{r['montant']:.2f} {data['params']['devise']} – {r['date']}")
            else:
                st.markdown('<div class="badge-warn">🟠 Vérification supplémentaire requise</div>',
                            unsafe_allow_html=True)
                st.caption("Référence trouvée, mais code invalide ou paiement non confirmé.")
        log("Vérification de document", ref_p or "-", "-", "consultation")


def page_parametres():
    header("Paramètres du moteur fiscal",
           "Modifiables uniquement par les utilisateurs autorisés – chaque changement est journalisé")
    if st.session_state["user"]["role"] != "Administrateur":
        st.error("Accès réservé à l'administrateur provincial.")
        return
    data = db()
    st.warning("Saisissez ici uniquement les valeurs issues des textes légaux approuvés.")
    with st.form("params"):
        cols = st.columns(3)
        nouveaux = {}
        for i, u in enumerate(USAGES):
            nouveaux[u] = cols[i].number_input(f"Taux IRL – {u} (%)", 0.0, 100.0,
                                               float(data["params"]["taux"][u]), 0.5)
        pot = st.number_input("Estimation du nombre total de biens locatifs (périmètre pilote)",
                              1, 10_000_000, int(data["params"]["potentiel_estime"]), 10)
        dev = st.selectbox("Devise d'affichage", ["USD", "CDF"],
                           index=["USD", "CDF"].index(data["params"]["devise"]))
        ok = st.form_submit_button("Enregistrer les paramètres", type="primary")
    if ok:
        for u in USAGES:
            if nouveaux[u] != data["params"]["taux"][u]:
                log("Modification d'un paramètre légal", f"taux {u}",
                    f"{data['params']['taux'][u]} %", f"{nouveaux[u]} %")
        if pot != data["params"]["potentiel_estime"]:
            log("Modification du potentiel estimé", "potentiel", data["params"]["potentiel_estime"], pot)
        if dev != data["params"]["devise"]:
            log("Modification de la devise", "devise", data["params"]["devise"], dev)
        data["params"] = {"taux": nouveaux, "devise": dev, "potentiel_estime": int(pot)}
        st.success("Paramètres enregistrés.")
        st.rerun()
    st.divider()
    if st.button("♻️ Réinitialiser les données de démonstration"):
        st.session_state.pop("db", None)
        st.rerun()


def page_audit():
    header("Journal d'audit", "Chaque opération sensible est tracée")
    a = pd.DataFrame(db()["audit"])
    c1, c2 = st.columns(2)
    users = c1.multiselect("Utilisateur", sorted(a["utilisateur"].unique()))
    q = c2.text_input("Recherche (action, dossier)")
    if users:
        a = a[a["utilisateur"].isin(users)]
    if q:
        a = a[a.apply(lambda r: q.lower() in f"{r['action']} {r['dossier']}".lower(), axis=1)]
    st.dataframe(a, hide_index=True)
    csv_button(a, "journal_audit.csv")


PAGE_FUNCS = {
    "📊 Tableau de bord": page_dashboard,
    "🏠 Registre des biens": page_registre,
    "📄 Contrats": page_contrats,
    "🧾 Déclarations & calcul": page_declarations,
    "💳 Paiements & quittances": page_paiements,
    "🔎 Contrôle & alertes": page_controle,
    "💰 Recouvrement": page_recouvrement,
    "🗺️ Carte & zones": page_carte,
    "✅ Vérification QR": page_qr,
    "⚙️ Paramètres": page_parametres,
    "🛡️ Journal d'audit": page_audit,
}


# ---------------------------------------------------------------------------
# AUTHENTIFICATION
# ---------------------------------------------------------------------------
def login_screen():
    st.markdown(
        '<div class="hero"><h1>🏛️ SUD-KIVU IRL DIGITAL</h1>'
        "<p>Plateforme provinciale de gestion de l'impôt sur le revenu locatif – DPMER</p>"
        "<p><b>Identifier – Fiabiliser – Recouvrer – Développer</b></p></div>",
        unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login"):
            st.subheader("Connexion sécurisée")
            login = st.text_input("Identifiant")
            pwd = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("Se connecter", type="primary")
        if ok:
            u = USERS.get(login.strip())
            if u and u[0] == h(pwd):
                st.session_state["user"] = dict(login=login.strip(), nom=u[1], role=u[2], commune=u[3])
                db()
                log("Connexion")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
        with st.expander("Comptes de démonstration"):
            st.markdown("""
| Identifiant | Mot de passe | Rôle |
|---|---|---|
| admin | admin123 | Administrateur provincial |
| direction | dpmer123 | Direction DPMER |
| chef.mul | chef123 | Chef de centre (Mulongwe) |
| agent024 | agent123 | Agent d'identification |
| controleur | ctrl123 | Agent de contrôle |
| recouvrement | recou123 | Agent de recouvrement |
| finance | fin123 | Responsable financier |
| auditeur | audit123 | Auditeur |
""")
            st.caption("Prototype : en production, utilisez JWT + authentification multifacteur (MFA).")


def main():
    if "user" not in st.session_state:
        login_screen()
        return
    user = st.session_state["user"]
    with st.sidebar:
        st.markdown("## 🏛️ SUD-KIVU IRL DIGITAL")
        st.caption("Gouvernement provincial du Sud-Kivu · DPMER")
        st.markdown(f"**{user['nom']}**  \n`{user['role']}`"
                    + (f"  \nRessort : {user['commune']}" if user["commune"] else ""))
        pages = PAGES_BY_ROLE[user["role"]]
        choix = st.radio("Navigation", pages, label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Déconnexion"):
            log("Déconnexion")
            st.session_state.pop("user")
            st.rerun()
        st.caption(f"Données de démonstration · {TODAY.strftime('%d/%m/%Y')}")
    PAGE_FUNCS[choix]()


main()
