import csv
import time

from multiprocessing import Process, Queue, cpu_count, log_to_stderr

from queue import Empty

from honeypot_detection import config

from sqlalchemy.orm import sessionmaker


EVENT_TYPE_EXIT = "exit"
EVENT_TYPE_WRITE = "write"


logger = log_to_stderr()


class Worker:

    def __init__(self, sqlalchemy_session, write_queue, yield_per):
        """
        :param sqlalchemy_session: to query the database (should be read only queries)
        :param write_queue: should put model instances
        :param yield_per: option to use when querying in batches
        """
        self.sqlalchemy_session = sqlalchemy_session
        self.write_queue = write_queue
        self.yield_per = yield_per

        self.logger = logger

    def send_output(self, output):
        self.write_queue.put({"event_type": EVENT_TYPE_WRITE, "row": output})

    def process_address(self, address):
        """
        Process a contract and write outputs in a queue.
        :param address: contract address to process
        """
        raise NotImplementedError


def worker_wrapper(read_queue, worker_class, write_queue, yield_per):
    logger.info("Worker started...")

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    # create the worker
    worker = worker_class(sqlalchemy_session, write_queue, yield_per)

    # while there are more addresses in the queue
    while True:
        # get the next address if possible
        try:
            address = read_queue.get(block=True, timeout=1)
            logger.debug("Next address: {}".format(address))

        # no more addresses in the queue
        except Empty:
            logger.info("No more addresses.")
            break

        # process the next address
        worker.process_address(address)

    sqlalchemy_session.close()
    sqlalchemy_engine.dispose()

    logger.info("Worker finished.")


def count_worker(queue, log_every=5):
    size = queue.qsize()
    last_size = size
    logger.info("{:d} remaining...".format(size))
    while size > 0:
        time.sleep(log_every)
        size = queue.qsize()
        processed = last_size - size
        logger.info("{:d} processed, {:d} remaining...".format(processed, size))
        last_size = size


def write_worker(queue, file_path, field_names):
    logger.info("Writing started...")

    f = open(file_path, "w")

    writer = csv.DictWriter(f, field_names)
    writer.writeheader()

    while True:
        # wait until there is a new event
        event = queue.get(block=True)

        # write event
        if event["event_type"] == EVENT_TYPE_WRITE:
            writer.writerow(event["row"])
        # exit event
        elif event["event_type"] == EVENT_TYPE_EXIT:
            break
        # something went wrong
        else:
            raise Exception("Invalid event type '{}'".format(event["event_type"]))

    f.close()

    logger.info("Writing finished.")


def multiprocess_by_address(addresses, worker_class, output_file_path, output_field_names, num_processes=None,
                            yield_per=10, log_every=5):
    """
    Addresses are put into a read queue.
    Several workers are spawn with one SQLAlchemy session each (should be used for read only queries).
    Each worker takes addresses from the read queue and puts outputs into a write queue (in dictionary format).
    After all the workers are done, the outputs are taken from write the queue and added to the session.
    At the end the session is committed.
    :param addresses: contract address to process
    :param worker_class: the one that actually does the processing
    :param output_file_path:
    :param output_field_names:
    :param num_processes: how many workers should be spawned
    :param yield_per: option to use when querying in batches
    :param log_every: amount of seconds between between count logs
    """
    start_time = time.time()

    if num_processes is None:
        num_processes = cpu_count() - 1

    read_queue = Queue()
    write_queue = Queue()

    # queue all the addresses
    for address in addresses:
        read_queue.put(address)

    # write worker: we will write in the output file using only one process and a queue
    write_process = Process(target=write_worker, args=(write_queue, output_file_path, output_field_names))
    write_process.start()

    # additional process to log the remaining addresses
    count_process = Process(target=count_worker, args=(read_queue, log_every))
    count_process.start()
    # we don't need to join this one

    # workers: we will process addresses in parallel
    worker_processes = []
    for _ in range(num_processes):
        worker_process = Process(target=worker_wrapper, args=(read_queue, worker_class, write_queue, yield_per))
        worker_process.start()
        worker_processes.append(worker_process)

    # wait for all the workers to finish
    logger.info("Waiting for the workers...")
    for worker_process in worker_processes:
        worker_process.join()
    logger.info("Workers finished.")

    # the workers stopped queuing rows
    # add to stop event for the writing worker
    write_queue.put({"event_type": EVENT_TYPE_EXIT})

    # wait until the writing worker actually stops
    write_process.join()

    # log the time
    elapsed_time = time.time() - start_time
    elapsed_time_unit = "seconds"
    if elapsed_time > 60:
        elapsed_time /= 60
        elapsed_time_unit = "minutes"
    if elapsed_time > 60:
        elapsed_time /= 60
        elapsed_time_unit = "hours"
    if elapsed_time > 24:
        elapsed_time /= 24
        elapsed_time_unit = "days"
    logger.info("Total time: {} {}".format(elapsed_time, elapsed_time_unit))
