"""
Serveur MCP : expose la file de publication à l'assistant.

Couche mince, volontairement. Aucune logique métier ici : chaque outil valide
le strict minimum, délègue à agenda/publisher/auth, et traduit les échecs en
`ToolError`. L'API MCP a déjà changé une fois sans prévenir (FastMCP renommé
MCPServer en 2.x) ; en gardant ce fichier sans substance, une future 3.x ne
coûtera qu'une réécriture d'une centaine de lignes, jamais du métier.

Pourquoi `ToolError` et pas une exception ordinaire : le SDK remplace toute
autre exception par « Error executing tool <nom> » et l'assistant ne voit rien
du message d'origine. Or ici les messages portent l'essentiel — ce qui a été
publié, ce qui reste à pousser, ce qu'il ne faut surtout pas relancer.

Lancement : python mcp_server.py   (transport stdio)
Dépendance : requirements-mcp.txt, jamais requirements.txt — la CI publie sans.
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import agenda
import auth
import publisher
import secret

serveur = MCPServer(
    name="post-agent",
    instructions=(
        "Agent de publication LinkedIn. La rédaction a lieu dans la conversation ; "
        "ces outils ne font que publier, programmer et consulter. "
        "La visibilité n'a jamais de valeur par défaut : demande-la si elle n'est pas dite."
    ),
)


def _traduire(exc):
    """Toute erreur attendue devient un ToolError, seul canal qui atteint l'assistant."""
    return ToolError(f"{type(exc).__name__} : {exc}")


@serveur.tool()
def publish_now(text: str, visibility: str) -> dict:
    """Publie un post immédiatement sur LinkedIn.

    `visibility` vaut PUBLIC ou CONNECTIONS et doit être fourni : ne devine pas.
    Si le retour contient `warning`, le post EST en ligne malgré l'anomalie —
    ne relance jamais l'outil dans ce cas, ce serait un doublon public.
    """
    try:
        return publisher.publish_now(text, visibility)
    except Exception as exc:
        raise _traduire(exc) from exc


@serveur.tool()
def schedule_post(text: str, scheduled_at: str, visibility: str) -> dict:
    """Programme un post et le pousse dans le dépôt.

    `scheduled_at` est une date ISO 8601 avec fuseau, par exemple
    2026-09-24T09:00:00+01:00. Sans fuseau, l'outil refuse.
    Le post n'est programmé que si `pushed` vaut vrai dans le retour.
    """
    try:
        return agenda.schedule_post(text, scheduled_at, visibility)
    except Exception as exc:
        raise _traduire(exc) from exc


@serveur.tool()
def list_queue() -> dict:
    """Liste les posts programmés, en cours, périmés, et les derniers publiés.

    `publishing` non vide signale une publication interrompue, `stale` des posts
    trop en retard pour partir : les deux demandent une décision humaine.
    """
    try:
        return agenda.list_queue()
    except Exception as exc:
        raise _traduire(exc) from exc


@serveur.tool()
def cancel_post(file: str) -> dict:
    """Annule un post programmé, désigné par son nom de fichier exact.

    Refuse si le post est déjà en cours de publication ou publié.
    """
    try:
        return agenda.cancel_post(file)
    except Exception as exc:
        raise _traduire(exc) from exc


@serveur.tool()
def auth_status() -> dict:
    """État du token LinkedIn et de sa copie dans les secrets GitHub.

    `secret_in_sync` vaut null quand GitHub est injoignable : c'est « inconnu »,
    pas « divergent ». S'il vaut false, la publication programmée cassera à
    l'expiration : relancer `python auth.py`.
    """
    try:
        token = auth.load_token()
        if not token:
            raise FileNotFoundError("token.json absent : lance python auth.py")
        jours = publisher.days_left()
        return {
            "name": token.get("name"),
            "person_urn": token.get("person_urn"),
            "expires_at": token.get("expires_at"),
            "days_left": jours,
            "secret_in_sync": secret.in_sync(token),
            "alerte": jours < 7,
        }
    except Exception as exc:
        raise _traduire(exc) from exc


if __name__ == "__main__":
    serveur.run(transport="stdio")
