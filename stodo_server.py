# coding: utf-8

import logging
import click

from sanic.exceptions import RequestTimeout, NotFound

from apps import createApp
from utils import RetCode, webJson, ParamsError


logger = logging.getLogger("apps")
app = createApp()


@app.exception(RequestTimeout)
def timeout(request, exception):
    return webJson(RetCode.REQUEST_TIMEOUT)


@app.exception(NotFound)
def notfound(request, exception):
    return webJson(RetCode.NOT_FOUND)


@app.exception(ParamsError)
def paramsError(request, exception):
    return webJson(RetCode.PARAMETER_ERROR, data=exception.data)


@app.exception(Exception)
def serverError(request, exception):
    logger.exception(exception)
    return webJson(RetCode.SERVER_ERROR)


@click.group()
def cli():
    pass


@cli.command(help="初始化数据库")
def initdb():
    from apps.models import S
    S.createAllTables()


@cli.command(help="运行server")
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8090)
def run(host, port):
    app.run(host=host, port=port, debug=True)


@cli.command(help="ipython命令行环境")
def ishell():
    from IPython import embed
    from apps.models import User, Role
    from apps import app
    embed()


if __name__ == "__main__":
    cli()
