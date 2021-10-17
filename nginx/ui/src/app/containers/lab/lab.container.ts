import {Component} from '@angular/core';
import {FormBuilder, FormControl, FormGroup, Validators} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {Observable, of, Subject, throwError} from 'rxjs';
import {catchError, delay} from 'rxjs/internal/operators';

@Component({
  selector: 'lab-page',
  templateUrl: './lab.container.html',
  styleUrls: ['./lab.container.css']
})
export class LabContainer {

  readonly currentTask$: Subject<string> = new Subject<string>();
  readonly formGroup: FormGroup;
  readonly configs$: Observable<string[]>;

  constructor(fb: FormBuilder, readonly http: HttpClient) {

    this.formGroup = fb.group({
      labs_count: ['', Validators.required],
      config: ['', Validators.required],
      dry_run: [false, Validators.required],
      logs_vv: [true, Validators.required]
    });

    this.configs$ = this.http.get<string[]>('/api/v1/configs')
      .pipe(
        catchError((error) => {
          alert(error.error);
          return throwError(error);
        })
      );
  }

  allTaskClickHandler() {

    const labsCountControl: FormControl = this.formGroup.get('labs_count') as FormControl;

    if (labsCountControl.disabled) {

      labsCountControl.enable();
    } else {

      labsCountControl.patchValue('all');
      labsCountControl.disable();
    }
  }

  startHandler() {

    let labsCount: string | string[] = this.formGroup.getRawValue().labs_count;
    if (labsCount !== 'all') {
      labsCount = (labsCount as string).split(/;|,|\s+/)
        .map((lab: string) => lab.trim())
        .filter((lab: string) => lab.length);
    }
    this.http.post<string>('/api/v1/labs', {...this.formGroup.value, labs_count: labsCount})
      .pipe(
        catchError((error) => {
          alert(error.error);
          return throwError(error);
        })
      )
      .subscribe((id: string) => {
        this.formGroup.disable();
        this.currentTask$.next(id);
      });
  }
}
