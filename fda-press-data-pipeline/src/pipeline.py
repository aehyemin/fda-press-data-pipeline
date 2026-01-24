import os

SCRIPTS = [
    "src/fda_press_collect.py",
    "src/fda_process.py",
    "src/fda_validate.py",
    "src/snowflake_load.py"
]

def main():
    for script in SCRIPTS:
        print(f" {script} 시작")
        
      
        exit_code = os.system(f"python3 {script}")
        
        if exit_code != 0:
            print(f"{script}에서 문제 발생. 중단.")
            return

    print("모든 작업 끝")

if __name__ == "__main__":
    main()