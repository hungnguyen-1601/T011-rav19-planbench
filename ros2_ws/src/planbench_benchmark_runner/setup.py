from setuptools import find_packages, setup

package_name = "planbench_benchmark_runner"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="PlanBench",
    maintainer_email="mebayluon@gmail.com",
    description="Runs PlanBench scenarios against a live Nav2 stack.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "runner_node = planbench_benchmark_runner.runner_node:main",
        ],
    },
)
