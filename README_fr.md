# 💬 SimpleX Chat pour Home Assistant

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]
![downloads][downloads-badge]

[![Ouvrez votre instance Home Assistant et ouvrez un dépôt dans le Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MX10-AC2N&repository=SimpleX-Chat_HA)

> 🇬🇧 **English version** : [README.md](README.md)

SimpleX Chat est une messagerie **sans identifiants utilisateur**, chiffrée de
bout en bout et avec un minimum de métadonnées. Cette intégration l'amène dans
Home Assistant comme un citoyen à part entière : un canal de notification
sécurisé pour la maison, une interface de messagerie pour une tablette
murale, et une cible pour les assistants vocaux et les agents IA.

---

## Ce que vous obtenez

**Messagerie**
- 🔎 Auto-découverte — les contacts et les groupes apparaissent d'eux-mêmes, plus de lien d'invitation à coller pour chacun
- 🔔 Une entité `notify.*` par contact ou groupe
- 💬 Messages entrants sous forme d'événements et de capteurs
- ⚡ Suivi de connexion en direct — un contact accepté pendant que HA tourne apparaît immédiatement

**Contenu**
- 🖼️ Images, audio et vidéo, envoyés comme du vrai contenu SimpleX et affichés en ligne
- 🔍 Recherche dans toutes les conversations, depuis la carte ou via un service
- 📊 Statistiques d'activité — messages par jour et par contact

**Home Assistant**
- 📇 Un device par contact : dernier message, compteur de non-lus, connectivité
- 🧩 10 services : envoi, recherche, statistiques, invitations, rafraîchissement, marquer comme lu…
- 🤖 Deux outils Assist/LLM : `send_simplex_message` et `search_simplex_messages`
- 📦 11 tableaux de bord prêts à l'emploi, du mur d'état au messager Glass
- 🌍 Français et anglais

---

## Démarrage

```bash
simplex-chat -p 5225
```

Puis ajoutez l'intégration :

**Paramètres → Appareils et services → Ajouter une integration → SimpleX Chat**,
et saisissez l'URL WebSocket (`ws://127.0.0.1:5225` par défaut).

Vos contacts sont découverts automatiquement — vous devriez voir une entité
`notify.simplex_chat_*` pour chacun d'eux quelques secondes plus tard.

Home Assistant tourne en Docker ? Le CLI tourne dans un conteneur séparé :
→ **[DOCKER.md](DOCKER.md)**.

---

## Prérequis

- **SimpleX Chat CLI** en mode WebSocket (`simplex-chat -p 5225`)
- Home Assistant **2025.8+**

Les tableaux de bord ont en plus besoin de deux cartes Lovelace de la
communauté — voir ci-dessous.

---

## Tableaux de bord

| Tableau de bord | [Mushroom][mushroom-url] | [Auto Entities][auto-entities-url] | Cartes SimpleX |
|-----------------|--------------------------|-----------------------------------|----------------|
| `simplex_fr.yaml` / `simplex_en.yaml` | – | ✅ obligatoire | – |
| `simplex_mushroom_fr.yaml` / `_en.yaml` | ✅ **obligatoire** | ✅ obligatoire | – |
| `simplex_auto_fr.yaml` / `_en.yaml` | – | – | ✅ obligatoire |
| `simplex_tablet_fr.yaml` | – | – | ✅ obligatoire (intercom) |
| `simplex_android_home_fr.yaml` | – | – | ✅ obligatoire |
| `simplex_android_look_fr.yaml` | – | – | ✅ obligatoire |

> ⚠️ **`simplex_mushroom_*.yaml` ne s'affiche pas du tout sans Mushroom.**
> Les cartes apparaissent comme « Custom element: mushroom-… » avec une
> erreur dans la console du navigateur.

Installez-le via HACS → *Intégrations* → **Mushroom** → téléchargement, puis
ajoutez `/local/mushroom.js` en **JavaScript Module** dans *Paramètres →
Tableaux de bord → Ressources*.

Détails : **[docs/dashboards.md](docs/dashboards.md)**.

---

## Documentation

| | |
|---|---|
| 📦 **[Installation](docs/installation.md)** | HACS, manuel, Docker, configuration du bridge |
| ⚙️ **[Configuration](docs/configuration.md)** | Auto-découverte, alias, contacts manuels |
| 💬 **[Utilisation](docs/usage.md)** | Services, événements, entités, recherche, images, statistiques, LLM |
| 🗂 **[Tableaux de bord & cartes](docs/dashboards.md)** | Les 11 tableaux de bord, le Messenger Glass, dépendances, mode dynamique |
| 🩺 **[Dépannage](docs/troubleshooting.md)** | Par symptôme : cartes vides, aucun message, compteurs à zéro… |
| 🛠 **[Développement](docs/development.md)** | Architecture, modules, tests, feuille de route |

---

## Crédits

- [SimpleX Chat](https://simplex.chat/) — la messagerie elle-même
- [Mushroom](https://github.com/piitaya/lovelace-mushroom) et [Auto Entities](https://github.com/thomasloven/lovelace-auto-entities) — les cartes Lovelace sur lesquelles reposent les tableaux de bord
- [simplex-bridge](https://github.com/MX10-AC2N/simplex-bridge) — le démon WebSocket de référence

## Licence

MIT — SimpleX Chat est un projet de [SimpleX Chat Ltd](https://simplex.chat/).
Cette intégration est un projet communautaire indépendant, sans affiliation
officielle.

<!-- Badges -->

[hacs-url]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/hacs-default-orange.svg?style=flat-square
[release-badge]: https://img.shields.io/github/v/release/MX10-AC2N/SimpleX-Chat_HA?style=flat-square
[downloads-badge]: https://img.shields.io/github/downloads/MX10-AC2N/SimpleX-Chat_HA/total?style=flat-square

<!-- References -->

[mushroom-url]: https://github.com/piitaya/lovelace-mushroom
[auto-entities-url]: https://github.com/thomasloven/lovelace-auto-entities
