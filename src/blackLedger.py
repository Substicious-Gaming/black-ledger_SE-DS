#region IMPORTS
import csv
import json
import re
import sys
import datetime
import json
import time
import shutil
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
#endregion

#region JSON Config Template
JSON_CFG = {
    "blackLedger": {
        "logs": {
            "file_extension": "log",
            "file_name": "SpaceEngineersDedicated_"
        },
        "entries": {
            "regex_patterns": {
                "date": "true",
                "time": "true",
                "player_id": "true"
            },
            "scan_previous_lines": "true",
            "lookback": 5
        },
        "ledger_output": {
            "file_type": "tsv",
            "file_name": "blackLedger"
        },
        "processed_logs": {
            "output_to_directory": "true",
            "output_directory": "./processed",
            "append_log_file": "true",
            "append_tag": "processed"
        },
        "prefabs": [
            "Prefab_SubType_Here",
            "Eco_Prefab_One"
        ]
  }
}
#endregion

@dataclass
class logTransactions:
    date: str
    time: str
    prefab: str
    value: int
    account_owner: str

#region Black Ledger Class
class blackLedger:

    #region blackLedger INIT
    def __init__(self, config_file="config.json"):

        self.config = self.cfg_load(config_file)
        self.prefabs = set(self.config['blackLedger'].get("prefabs", []))

        self._ext = self.config['blackLedger']['logs']['file_extension']
        self._log = self.config['blackLedger']['logs']['file_name']

        self._date = self.config['blackLedger']['entries']['regex_patterns']['date']
        self._time = self.config['blackLedger']['entries']['regex_patterns']['time']
        self._owner = self.config['blackLedger']['entries']['regex_patterns']['player_id']
        
        self._outdirBool = self.config['blackLedger']['processed_logs']['output_to_directory']
        self._outdir = self.config['blackLedger']['processed_logs']['output_directory']
        self._processedBool = self.config['blackLedger']['processed_logs']['append_log_file']
        self._processed = self.config['blackLedger']['processed_logs']['append_tag']

        self.type = self.config['blackLedger']['ledger_output']['file_type']
        self.output = self.config['blackLedger']['ledger_output']['file_name']

        self.lookbackBool = self.config['blackLedger']['entries']['scan_previous_lines']
        self.lookback = self.config['blackLedger']['entries']['lookback']

        self._output = self.output + "." + self.type
        
        # Purchase log line
        self.purchase_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2})\s+"          # Date
            r"(\d{2}:\d{2}):\d{2}\.\d+\s+"      # HH:MM
            r"-\s+Thread:\s+\d+\s+->\s+"
            r"SendBuyItemResult\s*-\s*Success,\s*"
            r"\d+,\s*"                         # Transaction ID
            r"([^,]+),\s*"                     # Prefab
            r"(\d+),\s*1\b"                    # Value
        )

        # Balance change line
        self.balance_pattern = re.compile(
            r"Balance change of\s+(-\d+)\s+"
            r"to account owner\s+(\d+)"
        )

        #self.write_output("csv")

        # Debug
        #print(json.dumps(self.config, indent=4))
        #print(self.config['blackLedger']['prefabs'])
        #print(f"Output file: {self._output}")


    #endregion

    #region Config Create/Load
    def cfg_create(self, filename:str) -> None:
        print(f"Creating new config file.")

        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(JSON_CFG, file, indent=4)
        
        time.sleep(2)

        path = Path(filename)

        if path.exists():
            print(f"Config has been created. You can now try again.")
            #sys.exit(1)

    def cfg_load(self, filename):
        
        path = Path(filename)

        if not path.exists():
            print(f"Config file '{filename}' not found.")
            self.cfg_create(filename)
            sys.exit(1)

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    #endregion

    #region Scan Single Log File
    def scan_logs(self, logfile):

        transactions = []

        if self.lookbackBool:
            previous_lines = deque(maxlen=self.lookback)
        else:
            previous_lines = deque(maxlen=0)

        with open(logfile, "r", encoding="utf-8", errors="ignore") as infile:
            for line in infile:
                purchase = self.purchase_pattern.search(line)

                if purchase:
                    date = purchase.group(1)
                    time = purchase.group(2)
                    prefab = purchase.group(3).strip()
                    value = int(purchase.group(4))

                    if prefab not in self.prefabs:
                        previous_lines.append(line)
                        continue
                
                    owner = ""

                    for previous in reversed(previous_lines):
                        balance = self.balance_pattern.search(previous)

                        if not balance:
                            continue
                        
                        amount = int(balance.group(1))

                        if amount == -value:
                            owner = balance.group(2)
                            break
                        
                    transactions.append(
                        logTransactions(
                            date=date,
                            time=time,
                            prefab=prefab,
                            value=value,
                            account_owner=f'Steam:{owner}'
                        )
                    )
                previous_lines.append(line)
        
        if self._processedBool:
            _logfile = logfile.stem+"_"+self._processed+".log"
        else:
            _logfile = logfile

        if self._outdirBool:
            if not os.path.exists(self._outdir):
                os.makedirs(self._outdir)

            shutil.move(
                str(logfile),
                os.path.join(self._outdir, str(_logfile))
            )        

        return transactions
    #endregion

#region Scan Mulitple Log Files
    def process_all_logs(self):

        root = Path.cwd()

        log_files = sorted(root.glob("*."+self._ext))

        if not log_files:
            print("No .log files found.")
            return

        for logfile in log_files:

            print(f"Scanning {logfile.name}")

            self.run(logfile)

        print()
        print(f"Processed {len(log_files)} log files.")
#endregion

    #region Write Output File
    def write_output(self, transactions, type):
        ext = type.lower()

        if not transactions:
            print("No matching transactions found.")
            return

        output_file = self._output

        if not Path.is_file(output_file):
            with open(output_file, "w", newline="", encoding="utf-8") as outfile:
                if ext == "csv":
                    writer = csv.writer(outfile, delimiter=',')
                elif ext == "tsv":
                    writer = csv.writer(outfile, delimiter='\t')
                
                if self._date and self._time and self._owner:
                    writer.writerow([
                        "Date",
                        "Time",
                        "Prefab",
                        "Value",
                        "AccountOwener"
                    ])
                elif self._time and self._owner and not self._date:
                    writer.writerow([
                        "Time",
                        "Prefab",
                        "Value",
                        "AccountOwener"
                    ])
                elif self._owner and not self._date and not self._time:
                    writer.writerow([
                        "Prefab",
                        "Value",
                        "AccountOwener"
                    ])
                elif not self._owner and not self._date and not self._time:
                    writer.writerow([
                        "Prefab",
                        "Value"
                    ])
                elif self._time and not self._owner and self._date:
                    writer.writerow([
                        "Date",
                        "Time",
                        "Prefab",
                        "Value"
                    ])
                elif self._owner and self._date and not self._time:
                    writer.writerow([
                        "Date",
                        "Prefab",
                        "Value",
                        "AccountOwener"
                    ])
                
                for t in transactions:
                    if self._date and self._time and self._owner:
                        writer.writerow([
                            t.date,
                            t.time,
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
                    elif self._time and self._owner and not self._date:
                        writer.writerow([
                            t.time,
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
                    elif self._owner and not self._date and not self._time:
                        writer.writerow([
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
                    elif not self._owner and not self._date and not self._time:
                        writer.writerow([
                            t.prefab,
                            t.value
                        ])
                    elif self._time and not self._owner and self._date:
                        writer.writerow([
                            t.date,
                            t.time,
                            t.prefab,
                            t.value
                        ])
                    elif self._owner and self._date and not self._time:
                        writer.writerow([
                            t.date,
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
            print(f"Wrote {len(transactions)} transactions.")
            print(f"Output file: {output_file}")
        else:
            with open(output_file, "a", newline="", encoding="utf-8") as outfile:
                if ext == "csv":
                    writer = csv.writer(outfile, delimiter=',')
                elif ext == "tsv":
                    writer = csv.writer(outfile, delimiter='\t')
                
                for t in transactions:
                    if self._date and self._time and self._owner:
                        writer.writerow([
                            t.date,
                            t.time,
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
                    elif self._time and self._owner and not self._date:
                        writer.writerow([
                            t.time,
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
                    elif self._owner and not self._date and not self._time:
                        writer.writerow([
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])
                    elif not self._owner and not self._date and not self._time:
                        writer.writerow([
                            t.prefab,
                            t.value
                        ])
                    elif self._time and not self._owner and self._date:
                        writer.writerow([
                            t.date,
                            t.time,
                            t.prefab,
                            t.value
                        ])
                    elif self._owner and self._date and not self._time:
                        writer.writerow([
                            t.date,
                            t.prefab,
                            t.value,
                            t.account_owner
                        ])

                print(f"Wrote {len(transactions)} transactions.")
                print(f"Output file: {output_file}")

    #endregion

    def readConfig(self):
        print(f"Logfile EXT: {self._ext}\nLogfile Name: {self._log}\nScan Previous Lines: {self.lookbackBool}\nOutput Ledger: {self._output}")

    def run(self, logfile):
        transactions = self.scan_logs(logfile)

        self.write_output(transactions, self.type)

#endregion
def main():

  

    print(f"\n\n  ____  _            _      _              _                 \n |  _ \\| |          | |    | |            | |                \n | |_) | | __ _  ___| | __ | |     ___  __| | __ _  ___ _ __ \n |  _ <| |/ _` |/ __| |/ / | |    / _ \\/ _` |/ _` |/ _ \\ '__|\n | |_) | | (_| | (__|   <  | |___|  __/ (_| | (_| |  __/ |   \n |____/|_|\\__,_|\\___|_|\\_\\ |______\\___|\\__,_|\\__, |\\___|_|   \n                                              __/ |          \n                              Version: 2.0.0 |___/           \n\n")

    ledger = blackLedger()

    if len(sys.argv) != 2 or sys.argv[1].lower() == "-help":
        print("Usage:")
        print("  python filescan.py <logfile>")
        print("  python filescan.py -all")
        sys.exit(1)

    arg = sys.argv[1]

    if arg.lower() == "-all":

        ledger.process_all_logs()
    #elif arg.lower() == "-config":
    #    ledger.readConfig()
    else:  
        logfile = Path(arg)

        if not logfile.exists():
            print(f"File not found: {logfile}")
            sys.exit(1)    

        ledger.run(logfile)

if __name__ == "__main__":
    main()