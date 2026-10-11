# MDP Reels

Crea in automatico un reel Instagram (1080x1920, formato MDP) per ogni articolo italiano
pubblicato su ilmagazinedelparrucchiere.com.

- Ogni 15 minuti GitHub Actions controlla gli articoli degli ultimi 3 giorni.
- Per ogni articolo nuovo crea `reels/<id articolo>.mp4` e lo pubblica su GitHub Pages.
- Lo scenario Make "MDP · Pubblica su Instagram dopo approvazione" usa il reel se esiste,
  altrimenti pubblica la copertina come foto.
- I reel vengono cancellati dopo 14 giorni.

Per rifare un reel: Actions > Reel MDP > Run workflow, con l'ID dell'articolo.

Font Oswald e Work Sans: SIL Open Font License 1.1.
