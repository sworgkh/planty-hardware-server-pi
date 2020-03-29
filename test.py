import queue
import datetime
import time


if __name__ == "__main__":
    q = queue.Queue(10)
    for x in range(100):
        item = {
            'timeStamp': datetime.datetime.utcnow(),
            'x': x
        }
        if q.full():
            while not q.empty():
                i = q.get()
                #print(f"{i.timeStamp} {i.x}")
                print(i)
        else:
            q.put(item)
        time.sleep(0.5)
