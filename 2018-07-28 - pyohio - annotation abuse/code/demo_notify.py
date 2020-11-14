from annotation_abuse.notify import notify


@notify
class MyClass:
    def __init__(self, x):
        self.x: "this one" = x
        self.y: int = 1


if __name__ == "__main__":
    foo = MyClass(3)
    for i in range(5):
        foo.x = i
