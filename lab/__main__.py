"""CLI entry point: stdlib-only prototype."""
import argparse
import errno
import json
from pathlib import Path

from .core import Lab


def main():
    p = argparse.ArgumentParser(description="Laboratório de Continuidade Intelectual — versão experimental")
    p.add_argument("--db", default="./data/continuum.sqlite", help="Caminho para SQLite")
    p.add_argument("--workspace", default=None, help="Diretório dedicado aos roteiros gerados")
    commands = p.add_subparsers(dest="command",required=True)
    server = commands.add_parser("serve")
    server.add_argument("--host","--bind",dest="host",default="127.0.0.1",help="Endereço de escuta (127.0.0.1 ou 0.0.0.0)")
    server.add_argument("--port",type=int,default=8767)
    server.add_argument("--scan-every",type=int,default=180)
    server.add_argument("--ollama-model",default="",help="LLM local opcional; mantém saídas hipotéticas")
    server.add_argument("--mcp-allow-writes",action="store_true",help="Permitir ferramentas de escrita no endpoint HTTP /mcp")
    server.add_argument("--mcp-token",default="",help="Token Bearer para autenticar o endpoint HTTP /mcp (ou via LAB_MCP_TOKEN)")
    mcp = commands.add_parser("mcp", help="Servidor MCP stdio (somente leitura por padrão)")
    mcp.add_argument("--allow-writes", action="store_true", help="Habilitar ferramentas de escrita")
    register = commands.add_parser("register")
    register.add_argument("path")
    register.add_argument("--label",default="Documentos")
    commands.add_parser("scan")
    commands.add_parser("verify")
    anchor = commands.add_parser("anchor")
    anchor.add_argument("--out",required=True)
    verify_anchor = commands.add_parser("verify-anchor")
    verify_anchor.add_argument("file")
    args=p.parse_args()
    lab = Lab(args.db,args.workspace)
    try:
        if args.command == "serve":
            from .server import serve
            try:
                serve(lab,host=args.host,port=args.port,scan_every=args.scan_every,ollama_model=args.ollama_model,
                      mcp_allow_writes=args.mcp_allow_writes,mcp_token=args.mcp_token)
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                p.exit(2, f"A porta {args.port} já está em uso. "
                       f"Se o CONTINUUM já estiver aberto, acesse http://{args.host}:{args.port}. "
                       "Para iniciar esta instância, encerre o processo que ocupa a porta "
                       "ou escolha outra com --port.\n")
            except KeyboardInterrupt:
                pass
        elif args.command == "mcp":
            from .mcp import serve
            serve(lab, allow_writes=args.allow_writes)
        elif args.command == "register":
            print(json.dumps(lab.register_source(args.path,args.label),ensure_ascii=False,indent=2))
        elif args.command == "scan":
            from .api import execute
            print(json.dumps(execute(lab, "scan", {}, allow_writes=True),ensure_ascii=False,indent=2))
        elif args.command == "verify":
            print(json.dumps(lab.verify(),ensure_ascii=False,indent=2))
        elif args.command == "anchor":
            path=Path(args.out).expanduser().resolve()
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open("x",encoding="utf-8") as f:
                json.dump(lab.anchor(),f,ensure_ascii=False,indent=2)
            print(path)
        elif args.command == "verify-anchor":
            anchor=json.loads(Path(args.file).read_text(encoding="utf-8"))
            print(json.dumps(lab.verify(anchor),ensure_ascii=False,indent=2))
    finally:
        lab.close()


if __name__ == "__main__":
    main()
