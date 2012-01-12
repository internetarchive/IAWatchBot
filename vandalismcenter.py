#!/usr/bin/env python

import web
import datetime
import re
import urllib
import lxml.html

urls = (
    "/", "index",
    "/diff(/.*)@(\d+)", "diff"
)
app = web.application(urls, globals())
db = web.database(dbn="postgres", db="vandalism", user="dmontalvo", pw="iawatchbot")

render = web.template.render("templates/", globals={
    "changequery": web.changequery,
    "url": web.url,
    "range": range
})

REPORTS_PER_PAGE = 50

def parse_datetime(value):
    """Creates datetime object from isoformat.
    
        >>> t = '2008-01-01T01:01:01.010101'
        >>> parse_datetime(t).isoformat()
        '2008-01-01T01:01:01.010101'
    """
    if isinstance(value, datetime.datetime):
        return value
    else:
        tokens = re.split('-|T|:|\.| ', value)
        return datetime.datetime(*map(int, tokens))

class index:
    def GET(self):
        i = web.input(page=1, display=None, problem=None, author=None)
        
        page = min(1, web.intget(i.page, 1))
        offset = (page-1) * REPORTS_PER_PAGE
        limit = REPORTS_PER_PAGE
        
        where = self.prepare_where(i)
        rowcount = db.select('reports', what='count(*) as count', where=where, vars=i)[0].count 
        npages = int(rowcount/REPORTS_PER_PAGE) + 1 # approx

        rows = db.select('reports', where=where, limit=limit, offset=offset, order="time desc", vars=i)
        
        rows = [self.process_row(row) for row in rows]
        status = any(not row.resolved for row in rows)
        return render.index(rows, status, page, npages, queryparams=web.input())
        
    def process_row(self, row):
        row.time = parse_datetime(row.time)
        if row.author.startswith("/people/"):
            row.author_name = row.author[len("/people/"):]
        else:
            row.author_name = None
        return row
        
    def prepare_where(self, i):
        where = '1 = 1'
        if i.display == 'all':
            pass
        elif i.display == 'resolved':
            where += ' AND resolved=1'
        else:
            where += ' AND resolved=0'
            
        if i.author:
            where += ' AND author=$author'
            
        if i.problem:
            where += ' AND problem=$problem'
        return where
            
    def POST(self):
        i = web.input(checkbox=[])
        db.update("reports", resolved=1, where="key in $checkbox", vars=i)
        raise web.seeother(web.ctx.fullpath)

class diff:
    def GET(self, key, rev):
        try:
            where = "key=$key AND revision=$rev"
            row = db.select('reports', where=where, limit=1, order="time desc", vars=locals())[0]
            row = index().process_row(row)
        except IndexError:
            raise web.notfound()
        
        url = "http://openlibrary.org%s?m=diff&b=%s" % (key, rev)
        html = urllib.urlopen(url).read()
        root = lxml.html.fromstring(html).get_element_by_id("contentBody")
        return render.diff(lxml.html.tostring(root), row, queryparams=web.input())
        
if __name__ == '__main__':
    app.run()
