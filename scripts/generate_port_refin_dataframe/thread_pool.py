"""
This module implements ThreadPool class.
"""

# built-in
from concurrent.futures import ThreadPoolExecutor, wait

# local
from scripts.generate_port_refin_dataframe.thread import Thread


class ThreadPool:
    """
    This class provides a simple way to add multiple threads to a pool,
    each thread is a function with args (Thread object). The class have
    an algorithm that is able to wrap the thread with an id to easily
    identify the response.
    """

    def __init__(self):
        self.threads = []
        self.current_id = 0
        self.result_map = {}

    def add_thread(self, function, *args) -> int:
        id = self.current_id
        self.current_id += 1
        thread = Thread(id, function, *args)
        self.threads.append(thread)
        return id

    def submit_all(self):
        with ThreadPoolExecutor() as executor:
            futures = []
            for thread in self.threads:
                future = executor.submit(self.wrap_function, thread)
                futures.append(future)

            print('%d threads started. Waiting for them...' % len(futures))
            wait(futures)

        results = [future.result() for future in futures]
        for result in results:
            thread_response = result[1] if isinstance(result[1], tuple) else [result[1]]
            self.result_map[result[0]] = thread_response

    def wrap_function(self, thread: Thread):
        response = thread.function(*thread.args)  # execute the function
        return thread.id, response

    def get(self, id: int):
        return self.result_map.get(id)
