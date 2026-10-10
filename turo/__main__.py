from turo import instance

if instance.claim():   # already running: that copy shows its window instead
    from turo.app import run
    run()
