from itertools import groupby
from typing import Any
from aqt import QWebEngineView, Qt, mw
from aqt.main import AnkiQt
from aqt.qt import QAction, QDialog, QVBoxLayout
from aqt.webview import AnkiWebView


class MainDialog(QDialog):

    def __init__(self, mw: AnkiQt) -> None:
        QDialog.__init__(self, parent=None)

        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.mw = mw
        self.deck = self.mw.col.decks.current()

        self.name = 'RetentionTable'
        self.setWindowTitle('Retention table')
        self.period = 0

        self.setObjectName('Dialog')
        self.resize(800, 600)

        self._add_webview()
        layout.addWidget(self.web)

        # debug
        #self.dev = QWebEngineView()
        #self.web.page().setDevToolsPage(self.dev.page())
        #self.dev.show()

        self.activateWindow()

    def _add_webview(self):
        self.web = AnkiWebView()

        self.web.set_bridge_command(self.onBridgeCmd, self)

        decks = self.get_data()

        style = """
            body {
                margin: 0;
            }
            table {
                width: 100%;
                table-layout: fixed;
                box-sizing: border-box;
                border-collapse: collapse;
            }
            td, th {
                overflow-wrap: break-word;
            }
            .alternate {
                background-color: #f0f0f0;
            }
            .night-mode .alternate {
                background-color: #555555;
            }
            .under {
                color: red;
                font-weight: bold;
            }
        """

        html_table = self.generate_html_table(decks)

        html = f"<style>{style}</style>" + html_table

        # pass `js` list to disable jquery loading
        self.web.stdHtml(html, js=[], context=self)

    def get_data(self):
        sql = """
            select a.deck_id, nt.name note_type_name, t.name card_type_name,
                   CAST(succ AS FLOAT) / (fail + succ) retention, fail, succ, (fail + succ) total
            from (
                select
                    c.did deck_id,
                    n.mid note_type_id,
                    c.ord card_type_id,
                    sum(case when r.ease = 1 and (r.type = 1 OR r.lastIvl <= -86400 OR r.lastIvl >= 1) then 1 else 0 end) fail,
                    sum(case when r.ease > 1 and (r.type = 1 OR r.lastIvl <= -86400 OR r.lastIvl >= 1) then 1 else 0 end) succ
                from revlog r
                join cards c
                on c.id = r.cid
                join notes n
                on n.id = c.nid
                where r.ease >= 1 and (r.type != 3 or r.factor != 0)
                group by c.did, c.ord
            ) a
            join templates t
              on t.ntid = a.note_type_id
             and t.ord = a.card_type_id
            join notetypes nt
              on nt.id = a.note_type_id
            """

        all_results = mw.col.db.all(sql)

        keys = ["deck_id", "note_type_name", "card_type_name", "retention", "fail", "succ", "total"]
        structured_results = [dict(zip(keys, row)) for row in all_results]

        data = []

        for result in structured_results:
            deck = mw.col.decks.get(result["deck_id"])
            config = mw.col.decks.get_config(deck["conf"])

            desired_retention = config["desiredRetention"] or 0
            retention = result["retention"] or 0

            check = retention < desired_retention

            data.append({
                "config_name": config["name"],
                "deck_name": deck["name"],
                "note_type_name": result["note_type_name"],
                "card_type_name": result["card_type_name"],
                "card_type_total": result["total"],
                "card_type_retention": round(retention, 3),
                "desired_retention": config["desiredRetention"],
                "check": check
            })

        data.sort(key=lambda x: (x['config_name'], x['deck_name']))

        return data

    def generate_html_table(self, data):
        html = """
        <table border="1" cellpadding="5" cellspacing="0">
        <thead>
            <tr>
                <th>Config Name</th>
                <th>Deck Name</th>
                <th>Note Type</th>
                <th>Card Type</th>
                <th>Total</th>
                <th>Retention</th>
                <th>Desired Retention</th>
            </tr>
        </thead>
        <tbody>
        """

        grouped_results = groupby(data, key=lambda x: x["config_name"])
        alternate = False

        for _, group in grouped_results:

            for item in group:
                html += f"""
                <tr class="{'alternate' if alternate else 'normal'}">
                    <td>{item['config_name']}</td>
                    <td>{item['deck_name']}</td>
                    <td>{item['note_type_name']}</td>
                    <td>{item['card_type_name']}</td>
                    <td>{item['card_type_total']}</td>
                    <td class="{'under' if item["check"] else 'over'}">{item['card_type_retention']}</td>
                    <td>{item['desired_retention']}</td>
                </tr>
                """
            alternate = not alternate

        html += """
        </tbody>
        </table>
        """

        return html

    def listToUser(self, l):
        def num_to_user(n) -> str:
            if n == round(n):
                return str(int(n))
            else:
                return str(n)

        return " ".join(map(num_to_user, l))

    def onBridgeCmd(self, cmd: str) -> Any:
        return 'Unhandled command: ' + cmd


def show_window():
    dialog = MainDialog(mw)
    dialog.show()


def add_menu_item():
    action = QAction("Retention table", mw)
    action.triggered.connect(show_window)
    mw.form.menuTools.addAction(action)


add_menu_item()
