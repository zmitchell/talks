from annotation_abuse.asts import inrange


@inrange
class MyClass:
    foo: "0 < foo < 3"


if __name__ == "__main__":
    bar = MyClass()
    for i in [1, 2, 3]:
        print(f"Setting bar.foo = {i}")
        bar.foo = i
