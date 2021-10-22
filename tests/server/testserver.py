from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Response, Header, Path, Query
from pydantic import BaseModel, confloat, conint, constr

app = FastAPI()


class EnergyLabel(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    X = "No registered label"


class WeekDay(str, Enum):
    Monday = "Monday"
    Tuesday = "Tuesday"
    Wednesday = "Wednesday"
    Thursday = "Thursday"
    Friday = "Friday"


class Message(BaseModel):
    message: str


class Detail(BaseModel):
    detail: str


class WageGroup(BaseModel):
    id: str
    # hourly_rate: confloat(ge=14.37, lt=50.00)
    hourly_rate: float


class EmployeeDetails(BaseModel):
    id: str
    name: str
    # login_name: constr(strip_whitespace=True, min_length=1, max_length=20)
    employee_number: int
    wagegroup_id: str
    parttime_day: Optional[WeekDay]


class Employee(BaseModel):
    name: str
    # login_name: constr(strip_whitespace=True, min_length=1, max_length=20)
    wagegroup_id: str
    parttime_day: Optional[WeekDay]


class EmployeeUpdate(BaseModel):
    name: Optional[str]
    # login_name: Optional[constr(strip_whitespace=True, min_length=1, max_length=20)]
    employee_number: Optional[int]
    wagegroup_id: Optional[str]
    parttime_day: Optional[WeekDay]


WAGE_GROUPS: Dict[str, WageGroup] = {}
EMPLOYEES: Dict[str, EmployeeDetails] = {}
EMPLOYEE_NUMBERS = iter(range(1, 1000))
ENERGY_LABELS: Dict[str, Dict[int, Dict[str, EnergyLabel]]] = {
    "1111AA": {
        10: {
            "": EnergyLabel.A,
            "C": EnergyLabel.C,
        },
    }
}


@app.get("/", status_code=200, response_model=Message)
def get_root(*, name_from_header: str = Header(""), title: str = Header("")) -> Message:
    name = name_from_header if name_from_header else "stranger"
    return Message(message=f"Welcome {title}{name}!")


@app.get(
    "/message",
    status_code=200,
    response_model=Message,
    responses={403: {"model": Detail}}
)
def get_message(*, secret_code: int = Header(...)) -> Message:
    if secret_code != 42:
        raise HTTPException(status_code=403, detail="Incorrect code!")
    return Message(message="Welcome, agent HAL")


@app.get(
    "/energy_label/{zipcode}/{home_number}",
    status_code=200,
    response_model=Message,
)
def get_energy_label(
    zipcode: str = Path(..., min_length=6, max_length=6),
    home_number: int = Path(..., ge=1),
    extension: Optional[str] = Query(None, min_length=1, max_length=99),
) -> Message:
    if not (labels_for_zipcode := ENERGY_LABELS.get(zipcode)):
        return Message(message=EnergyLabel.X)
    if not (labels_for_home_number := labels_for_zipcode.get(home_number)):
        return Message(message=EnergyLabel.X)
    extension = "" if extension is None else extension
    return Message(message=labels_for_home_number.get(extension, EnergyLabel.X))


@app.post(
    "/wagegroups",
    status_code=201,
    response_model=WageGroup,
    responses={418: {"model": Detail}},
)
def post_wagegroup(wagegroup: WageGroup) -> WageGroup:
    if wagegroup.id in WAGE_GROUPS.keys():
        raise HTTPException(status_code=418, detail="Wage group already exists.")
    WAGE_GROUPS[wagegroup.id] = wagegroup
    return wagegroup


@app.get(
    "/wagegroups/{wagegroup_id}",
    status_code=200,
    response_model=WageGroup,
    responses={404: {"model": Detail}},
)
def get_wagegroup(wagegroup_id: str) -> WageGroup:
    if wagegroup_id not in WAGE_GROUPS.keys():
        raise HTTPException(status_code=404, detail="Wage group not found")
    return WAGE_GROUPS[wagegroup_id]


@app.put(
    "/wagegroups/{wagegroup_id}",
    status_code=200,
    response_model=WageGroup,
    responses={404: {"model": Detail}},
)
def put_wagegroup(wagegroup_id: str, wagegroup: WageGroup) -> WageGroup:
    if wagegroup_id not in WAGE_GROUPS.keys():
        raise HTTPException(status_code=404, detail="Wage group not found.")
    WAGE_GROUPS[wagegroup.id] = wagegroup
    return wagegroup


@app.delete(
    "/wagegroups/{wagegroup_id}",
    status_code=204,
    response_class=Response,
    responses={404: {"model": Detail}, 406: {"model": Detail}},
)
def delete_wagegroup(wagegroup_id: str) -> None:
    if wagegroup_id not in WAGE_GROUPS.keys():
        raise HTTPException(status_code=404, detail="Wage group not found.")
    used_by = [e for e in EMPLOYEES.values() if e.wagegroup_id == wagegroup_id]
    if used_by:
        raise HTTPException(
            status_code=406,
            detail=f"Wage group still in use by {len(used_by)} employees.",
        )
    WAGE_GROUPS.pop(wagegroup_id)


@app.post(
    "/employees",
    status_code=201,
    response_model=EmployeeDetails,
    responses={451: {"model": Detail}},
)
def post_employee(employee: Employee) -> EmployeeDetails:
    wagegroup_id = employee.wagegroup_id
    if wagegroup_id not in WAGE_GROUPS.keys():
        raise HTTPException(
            status_code=451, detail=f"Wage group with id {wagegroup_id} does not exist."
        )
    new_employee = EmployeeDetails(
        id=uuid4().hex,
        employee_number=next(EMPLOYEE_NUMBERS),
        **employee.dict(),
    )
    EMPLOYEES[new_employee.id] = new_employee
    return new_employee


@app.get(
    "/employees/{employee_id}",
    status_code=200,
    response_model=EmployeeDetails,
    responses={404: {"model": Detail}},
)
def get_employee(employee_id: str) -> EmployeeDetails:
    if employee_id not in EMPLOYEES.keys():
        raise HTTPException(status_code=404, detail="Employee not found")
    return EMPLOYEES[employee_id]


@app.patch(
    "/employees/{employee_id}",
    status_code=200,
    response_model=EmployeeDetails,
    responses={404: {"model": Detail}},
)
def patch_employee(employee_id: str, employee: EmployeeUpdate) -> EmployeeDetails:
    if employee_id not in EMPLOYEES.keys():
        raise HTTPException(status_code=404, detail="Employee not found")
    stored_employee_data = EMPLOYEES[employee_id]
    employee_update_data = employee.dict(exclude_unset=True)
    updated_employee = stored_employee_data.copy(update=employee_update_data)
    EMPLOYEES[employee_id] = updated_employee
    return updated_employee


@app.get("/available_employees", status_code=200, response_model=List[EmployeeDetails])
def get_available_employees(weekday: WeekDay = Query(...)) -> List[EmployeeDetails]:
    return [e for e in EMPLOYEES.values() if e.parttime_day != weekday]


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
