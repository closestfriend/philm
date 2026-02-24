"""UI subcommand — launches the Philm web interface."""

import typer
import uvicorn

app = typer.Typer(name="ui", help="Launch the Philm web UI")


@app.callback(invoke_without_command=True)
def launch(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
):
    """Launch the Philm web interface at http://localhost:8000"""
    typer.echo(f"Starting Philm UI at http://{host}:{port}")
    uvicorn.run(
        "video_analyzer.ui:app",
        host=host,
        port=port,
        reload=reload,
    )
