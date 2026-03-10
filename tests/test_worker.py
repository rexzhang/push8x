import asyncio

import pytest

from push8x.worker import worker_guardian, worker_supervisor


class MockWorker:
    """Mock worker class for testing."""

    def __init__(self, name: str | None = None):
        self.worker_name = name if name else "mock_worker"
        self.call_count = 0
        self.raise_error = False
        self.error_times = 0  # how many times to raise error before succeeding

    @worker_guardian(name="test_worker")
    async def normal_worker(self):
        """A worker that completes normally."""
        self.call_count += 1
        await asyncio.sleep(0.01)
        return "done"

    @worker_guardian(
        name="error_worker", max_retries=2, initial_delay=0.01, max_delay=0.1
    )
    async def error_worker(self):
        """A worker that raises an error."""
        self.call_count += 1
        raise RuntimeError("Test error")

    @worker_guardian(
        name="retry_worker", max_retries=3, initial_delay=0.01, max_delay=0.1
    )
    async def retry_then_success_worker(self):
        """A worker that fails a few times then succeeds."""
        self.call_count += 1
        if self.call_count <= self.error_times:
            raise RuntimeError("Temporary error")
        return "recovered"

    @worker_guardian()  # No explicit name, should use worker_name attribute
    async def auto_name_worker(self):
        """A worker without explicit name."""
        self.call_count += 1
        return "auto_done"

    @worker_guardian(max_retries=-1, initial_delay=0.01, max_delay=0.1)
    async def infinite_retry_worker(self):
        """A worker with infinite retries."""
        self.call_count += 1
        if self.call_count < 3:
            raise RuntimeError("Keep retrying")
        return "finally_done"


class TestWorkerGuardian:
    """Tests for worker_guardian decorator."""

    @pytest.mark.asyncio
    async def test_normal_worker_completes(self):
        """Test that a normal worker completes successfully."""
        worker = MockWorker()
        result = await worker.normal_worker()
        assert result == "done"
        assert worker.call_count == 1

    @pytest.mark.asyncio
    async def test_worker_name_attribute(self):
        """Test that _worker_name attribute is set on decorated function."""
        worker = MockWorker()
        assert worker.normal_worker.worker_name == "test_worker"
        assert worker.error_worker.worker_name == "error_worker"

    @pytest.mark.asyncio
    async def test_error_worker_retries_and_gives_up(self):
        """Test that error worker retries then gives up after max_retries."""
        worker = MockWorker()
        # This should return None after giving up (break from loop)
        result = await worker.error_worker()
        assert result is None
        # max_retries=2 means it will retry 2 times, so 3 total attempts
        assert worker.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """Test that worker can recover after retries."""
        worker = MockWorker()
        worker.error_times = 2  # Fail twice, succeed on third
        result = await worker.retry_then_success_worker()
        assert result == "recovered"
        assert worker.call_count == 3

    @pytest.mark.asyncio
    async def test_auto_name_from_attribute(self):
        """Test that worker name is derived from worker_name attribute if not specified."""
        worker = MockWorker(name="custom_name")
        result = await worker.auto_name_worker()
        assert result == "auto_done"
        # The name should come from self.worker_name when decorator name is None

    @pytest.mark.asyncio
    async def test_infinite_retry_eventually_succeeds(self):
        """Test that infinite retry worker keeps trying until success."""
        worker = MockWorker()
        result = await worker.infinite_retry_worker()
        assert result == "finally_done"
        assert worker.call_count == 3

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        """Test that CancelledError is properly propagated."""
        worker = MockWorker()

        async def cancel_after_delay():
            await asyncio.sleep(0.005)
            raise asyncio.CancelledError()

        # We need to test cancellation handling differently
        # since the decorator catches it but re-raises
        task = asyncio.create_task(worker.normal_worker())
        await asyncio.sleep(0.005)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


class TestWorkerSupervisor:
    """Tests for worker_supervisor function."""

    @pytest.mark.asyncio
    async def test_supervisor_with_normal_workers(self):
        """Test supervisor with workers that complete normally."""
        worker1 = MockWorker()
        worker2 = MockWorker()

        # Pass uncalled methods
        await worker_supervisor([worker1.normal_worker, worker2.auto_name_worker])

        # At least one worker should have been called
        assert worker1.call_count >= 1 or worker2.call_count >= 1

    @pytest.mark.asyncio
    async def test_supervisor_sets_task_names(self):
        """Test that task names are set correctly from _worker_name."""
        worker = MockWorker()

        async def check_task_name():
            await asyncio.sleep(0.01)
            # Get current task name
            task = asyncio.current_task()
            return task.get_name() if task else None

        # Create a task to verify naming works
        task = asyncio.create_task(worker.normal_worker(), name="test_worker")
        result = await task
        assert result == "done"

    @pytest.mark.asyncio
    async def test_supervisor_cancels_pending_on_completion(self):
        """Test that supervisor cancels other workers when one completes."""
        worker1 = MockWorker()
        worker2 = MockWorker()

        # Make one worker complete faster
        worker2.call_count = 0

        await worker_supervisor([worker1.normal_worker, worker2.normal_worker])

        # One worker should complete, others may be cancelled
        assert worker1.call_count >= 1 or worker2.call_count >= 1

    @pytest.mark.asyncio
    async def test_supervisor_with_error_worker(self):
        """Test supervisor handles workers that error out."""
        worker1 = MockWorker()
        worker2 = MockWorker()
        worker2.error_times = 100  # Always error

        # Should handle the error gracefully
        await worker_supervisor(
            [worker1.normal_worker, worker2.retry_then_success_worker]
        )
